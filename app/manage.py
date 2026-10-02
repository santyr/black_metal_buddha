from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from .catalog import get_product
from .catalog_ops import (
    assert_production_catalog,
    catalog_errors,
    catalog_fingerprint,
    catalog_manifest,
    import_catalog_manifest,
)
from .db import SessionLocal
from .fulfillment.printful import PrintfulClient
from .models import Job, Order, ProductVariant
from .ops import build_attention_report
from .orders import (
    create_order,
    set_shipping_rate,
    set_square_checkout,
    sync_square_pricing,
    validate_pending_catalog,
)
from .payments.square import SquareClient
from .reconcile import reconcile_orders, reconcile_printful_order, reconcile_square_order
from .refunds import request_refund
from .schemas import CreateOrderIn
from .settings import settings


def seed_sandbox_variant(args: argparse.Namespace) -> None:
    if settings.app_env == "production":
        raise SystemExit("Sandbox variant seeding is disabled in production.")
    with SessionLocal() as session:
        if get_product(args.product_slug, session) is None:
            raise SystemExit(f"Unknown product slug: {args.product_slug}")
        existing = session.scalar(select(ProductVariant).where(ProductVariant.sku == args.sku))
        if existing:
            raise SystemExit(f"SKU already exists: {args.sku}")

        variant = ProductVariant(
            product_slug=args.product_slug,
            sku=args.sku,
            size=args.size,
            color=args.color,
            currency="USD",
            retail_price_cents=args.price_cents,
            active=True,
            sellable=True,
            printful_product_id=args.printful_product_id,
            printful_variant_id=args.printful_variant_id,
        )
        session.add(variant)
        session.commit()
        print(f"Created sandbox SKU {variant.sku} at ${variant.retail_price_cents / 100:.2f}")


def list_orders(_: argparse.Namespace) -> None:
    with SessionLocal() as session:
        orders = session.scalars(select(Order).order_by(Order.created_at.desc()).limit(100)).all()
        if not orders:
            print("No orders.")
            return
        for order in orders:
            print(
                order.order_number,
                "CANARY" if order.is_canary else "ORDER",
                order.order_state,
                order.payment_state,
                order.fulfillment_state,
                order.refund_state,
                f"{order.currency} {order.total_cents / 100:.2f}",
            )


def reconcile(_: argparse.Namespace) -> None:
    square = None
    printful = None

    if settings.square_access_token and settings.square_location_id:
        square = SquareClient()
    if settings.printful_mode != "disabled" and settings.printful_token:
        printful = PrintfulClient()

    if square is None and printful is None:
        raise SystemExit("No configured provider is available for reconciliation.")

    with SessionLocal() as session:
        counts = reconcile_orders(
            session,
            square_client=square,
            printful_client=printful,
        )
    print(counts)


def checkout_input(args: argparse.Namespace) -> CreateOrderIn:
    with SessionLocal() as session:
        variant = session.scalar(select(ProductVariant).where(ProductVariant.sku == args.sku))
        variant_id = variant.printful_variant_id if variant else None
    return CreateOrderIn(
        recipient={
            "name": args.name,
            "email": args.email,
            "phone": args.phone,
            "address1": args.address1,
            "address2": args.address2,
            "city": args.city,
            "state": args.state,
            "postal_code": args.postal_code,
            "country_code": args.country,
        },
        items=[{"sku": args.sku, "quantity": args.quantity, "printful_variant_id": variant_id}],
    )


def create_checkout_from_cli(args: argparse.Namespace, *, is_canary: bool) -> Order:
    data = checkout_input(args)
    with SessionLocal() as session:
        if is_canary:
            assert_production_catalog(session, settings.production_catalog_fingerprint)

        order = create_order(session, data, is_canary=is_canary)
        printful = PrintfulClient()
        rates = printful.get_shipping_rates(order)
        if not rates:
            raise SystemExit("Printful returned no shipping rates")

        selected = next((rate for rate in rates if rate["shipping"] == args.shipping), None)
        if selected is None:
            available = ", ".join(rate["shipping"] for rate in rates)
            raise SystemExit(
                f"Shipping method {args.shipping!r} unavailable. Available: {available}"
            )

        set_shipping_rate(
            session,
            order,
            shipping_method=selected["shipping"],
            shipping_cents=selected["rate_cents"],
            currency=selected["currency"],
        )

        square = SquareClient()
        validate_pending_catalog(session, order)
        link = square.create_payment_link(order)
        square_order = square.get_order(link["order_id"])
        sync_square_pricing(session, order, square_order)
        set_square_checkout(
            session,
            order,
            payment_link_id=link["id"],
            square_order_id=link["order_id"],
            checkout_url=link["url"],
        )

        print(f"Order: {order.order_number}")
        print(f"Mode: {'LIVE PRODUCTION CANARY' if is_canary else 'SANDBOX'}")
        print(f"Subtotal: {order.currency} {order.subtotal_cents / 100:.2f}")
        print(
            f"Shipping: {order.currency} {order.shipping_cents / 100:.2f} "
            f"({order.shipping_method})"
        )
        print(f"Square tax: {order.currency} {order.tax_cents / 100:.2f}")
        print(f"Total: {order.currency} {order.total_cents / 100:.2f}")
        print(f"Checkout: {order.square_checkout_url}")
        return order


def sandbox_checkout(args: argparse.Namespace) -> None:
    if settings.app_env == "production" or settings.square_environment != "sandbox":
        raise SystemExit("sandbox-checkout requires APP_ENV != production and Square sandbox")
    if not settings.printful_token:
        raise SystemExit("PRINTFUL_TOKEN is required to quote shipping")
    create_checkout_from_cli(args, is_canary=False)


def production_canary(args: argparse.Namespace) -> None:
    if not args.i_understand_this_is_live:
        raise SystemExit(
            "Refusing live canary. Re-run with --i-understand-this-is-live "
            "only when a real Square charge and Printful fulfillment are intended."
        )
    settings.validate_canary_safety()
    order = create_checkout_from_cli(args, is_canary=True)
    print()
    print("LIVE CANARY CREATED.")
    print("Pay the Square checkout yourself, then allow the worker/reconciliation timer to run.")
    print(f"Check with: python -m app.manage canary-status {order.order_number}")


def canary_status(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        order = session.scalar(select(Order).where(Order.order_number == args.order_number))
        if order is None:
            raise SystemExit("Order not found")
        if not order.is_canary:
            raise SystemExit("Refusing: order is not marked as a canary")

        if order.square_order_id and settings.square_access_token:
            reconcile_square_order(session, order, client=SquareClient())
        if order.payment_state == "COMPLETED" and settings.printful_token:
            reconcile_printful_order(session, order, client=PrintfulClient())

        jobs = session.scalars(select(Job).where(Job.order_id == order.id)).all()
        failed = [job for job in jobs if job.state == "FAILED"]
        email_jobs = [job for job in jobs if job.job_type == "SEND_ORDER_CONFIRMATION"]

        checks = {
            "payment_completed": order.payment_state == "COMPLETED",
            "printful_confirmed": order.printful_confirmed_at is not None,
            "printful_cost_known": order.printful_cost_cents is not None,
            "printful_cost_within_retail": (
                order.printful_cost_cents is not None
                and order.printful_cost_cents <= order.total_cents
            ),
            "no_failed_jobs": not failed,
            "confirmation_email_completed": bool(email_jobs)
            and all(job.state == "COMPLETED" for job in email_jobs),
            "fulfillment_started": order.fulfillment_state
            in {"PENDING", "INREVIEW", "INPROCESS", "ONHOLD", "PARTIAL", "FULFILLED"},
        }
        print(json.dumps(
            {
                "order_number": order.order_number,
                "order_state": order.order_state,
                "payment_state": order.payment_state,
                "fulfillment_state": order.fulfillment_state,
                "printful_cost_cents": order.printful_cost_cents,
                "retail_total_cents": order.total_cents,
                "checks": checks,
            },
            indent=2,
            sort_keys=True,
        ))
        if not all(checks.values()):
            raise SystemExit(2)


def refund_order(args: argparse.Namespace) -> None:
    if settings.square_environment != "sandbox":
        raise SystemExit("refund-order is sandbox-only; use the gated admin UI in production")

    with SessionLocal() as session:
        order = session.scalar(select(Order).where(Order.order_number == args.order_number))
        if order is None:
            raise SystemExit("Order not found")

        refund = request_refund(
            session,
            order,
            amount_cents=args.amount_cents,
            reason=args.reason,
            client=SquareClient(),
        )
        print(
            refund.square_refund_id,
            refund.status,
            f"{refund.currency} {refund.amount_cents / 100:.2f}",
        )


def ops_report(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        report = build_attention_report(session)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        counts = report["counts"]
        print(f"Attention items: {counts['attention_total']}")
        for issue in report["issues"]:
            print(issue["kind"], issue["order_number"], issue["detail"])

    if args.fail_on_attention and report["counts"]["attention_total"]:
        raise SystemExit(2)


def catalog_validate(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        errors = catalog_errors(session)
        fingerprint = catalog_fingerprint(session)
    print(f"fingerprint={fingerprint}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(2)
    if args.expect and fingerprint != args.expect.lower():
        print(f"ERROR: expected fingerprint {args.expect}, got {fingerprint}")
        raise SystemExit(2)
    print("Catalog valid.")


def catalog_export(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        manifest = catalog_manifest(session)
        fingerprint = catalog_fingerprint(session)
    path = Path(args.path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    print(f"sellable_fingerprint={fingerprint}")


def catalog_import(args: argparse.Namespace) -> None:
    if settings.printful_catalog_sync_enabled:
        raise SystemExit("Manage products in Printful while automatic catalog sync is enabled")
    if settings.app_env == "production" and settings.phase1_api_enabled:
        raise SystemExit("Disable public production checkout before importing catalog data")
    manifest = json.loads(Path(args.path).read_text(encoding="utf-8"))
    with SessionLocal() as session:
        result = import_catalog_manifest(session, manifest, apply=args.apply)
        if args.apply:
            errors = catalog_errors(session)
            if errors:
                raise SystemExit("Imported catalog is invalid: " + "; ".join(errors))
            fingerprint = catalog_fingerprint(session)
        else:
            fingerprint = None
    print(json.dumps(result, indent=2))
    if args.apply:
        print(f"sellable_fingerprint={fingerprint}")
    else:
        print("Dry run only. Re-run with --apply to persist.")


def sync_printful_catalog(args: argparse.Namespace) -> None:
    from .printful_catalog import CatalogSyncError, sync_catalog
    try:
        with SessionLocal() as session:
            result = sync_catalog(session, apply=not args.dry_run)
    except CatalogSyncError as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, sort_keys=True))


def printful_catalog_status(_: argparse.Namespace) -> None:
    from .models import PrintfulCatalogState
    with SessionLocal() as session:
        state = session.get(PrintfulCatalogState, 1)
        print(json.dumps({"enabled": settings.printful_catalog_sync_enabled,
                          "store_matches": bool(state and state.store_id == settings.printful_store_id),
                          "synced_at": state.synced_at.isoformat() if state else None,
                          "products": state.product_count if state else 0,
                          "variants": state.variant_count if state else 0}, sort_keys=True))


def add_checkout_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sku", required=True)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--shipping", default="STANDARD")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone")
    parser.add_argument("--address1", required=True)
    parser.add_argument("--address2")
    parser.add_argument("--city", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--postal-code", required=True)
    parser.add_argument("--country", default="US")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Black Metal Buddha backend management")
    sub = p.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed-sandbox-variant")
    seed.add_argument("--product-slug", required=True)
    seed.add_argument("--sku", required=True)
    seed.add_argument("--size", required=True)
    seed.add_argument("--color", default="Black")
    seed.add_argument("--price-cents", type=int, required=True)
    seed.add_argument("--printful-product-id")
    seed.add_argument("--printful-variant-id")
    seed.set_defaults(func=seed_sandbox_variant)

    ls = sub.add_parser("list-orders")
    ls.set_defaults(func=list_orders)

    rec = sub.add_parser("reconcile")
    rec.set_defaults(func=reconcile)

    checkout = sub.add_parser("sandbox-checkout")
    add_checkout_arguments(checkout)
    checkout.set_defaults(func=sandbox_checkout)

    canary = sub.add_parser("production-canary")
    add_checkout_arguments(canary)
    canary.add_argument("--i-understand-this-is-live", action="store_true")
    canary.set_defaults(func=production_canary)

    canary_check = sub.add_parser("canary-status")
    canary_check.add_argument("order_number")
    canary_check.set_defaults(func=canary_status)

    refund = sub.add_parser("refund-order")
    refund.add_argument("order_number")
    refund.add_argument("--amount-cents", type=int)
    refund.add_argument("--reason", default="Customer refund")
    refund.set_defaults(func=refund_order)

    ops = sub.add_parser("ops-report")
    ops.add_argument("--json", action="store_true")
    ops.add_argument("--fail-on-attention", action="store_true")
    ops.set_defaults(func=ops_report)

    validate = sub.add_parser("catalog-validate")
    validate.add_argument("--expect")
    validate.set_defaults(func=catalog_validate)

    export = sub.add_parser("catalog-export")
    export.add_argument("path")
    export.set_defaults(func=catalog_export)

    importer = sub.add_parser("catalog-import")
    importer.add_argument("path")
    importer.add_argument("--apply", action="store_true")
    importer.set_defaults(func=catalog_import)

    sync = sub.add_parser("sync-printful-catalog")
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=sync_printful_catalog)

    status = sub.add_parser("printful-catalog-status")
    status.set_defaults(func=printful_catalog_status)

    return p


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
