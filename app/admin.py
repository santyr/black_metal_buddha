from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .admin_auth import csrf_token, require_admin, verify_csrf
from .audit import record_audit
from .branding import LOGO_PATH, LOGO_TYPE
from .catalog import products_by_slug
from .db import SessionLocal
from .fulfillment.printful import PrintfulClient
from .models import (
    AuditLog,
    FulfillmentEvent,
    Job,
    Order,
    PaymentEvent,
    ProductVariant,
    Refund,
)
from .ops import build_attention_report
from .payments.square import SquareClient
from .payments.paypal import PayPalClient
from .payments.paypal_capture import capture_paypal_order
from .reconcile import reconcile_printful_order, reconcile_square_order
from .refunds import RefundError, request_refund
from .settings import settings

ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=ROOT / "app" / "templates")
router = APIRouter(prefix="/admin", tags=["admin"], include_in_schema=False)


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def admin_context(request: Request, actor: str, **kwargs):
    return {
        "request": request,
        "actor": actor,
        "site_name": "Black Metal Buddha",
        "logo_path": LOGO_PATH,
        "logo_type": LOGO_TYPE,
        "phase1_enabled": settings.phase1_api_enabled,
        "settings": settings,
        **kwargs,
    }


def redirect(path: str, message: str | None = None) -> RedirectResponse:
    if message:
        separator = "&" if "?" in path else "?"
        path += separator + "message=" + quote_plus(message[:300])
    return RedirectResponse(path, status_code=303)


def require_catalog_writable() -> None:
    if settings.printful_catalog_sync_enabled:
        raise HTTPException(status_code=409, detail="Manage products in Printful")
    if settings.app_env == "production" and settings.phase1_api_enabled:
        raise HTTPException(
            status_code=409,
            detail="Catalog edits require production checkout to be disabled",
        )


def get_order_or_404(session: Session, order_number: str) -> Order:
    order = session.scalar(select(Order).where(Order.order_number == order_number))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def money_to_cents(value: str) -> int:
    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("Invalid price") from exc
    if not amount.is_finite() or amount < 0 or amount > 100_000:
        raise ValueError("Price is outside the allowed range")
    cents = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return cents


def checkbox(form, name: str) -> bool:
    return str(form.get(name) or "").lower() in {"1", "true", "yes", "on"}


@router.get("")
def dashboard(
    request: Request,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    report = build_attention_report(session)
    recent_orders = session.scalars(
        select(Order).order_by(Order.created_at.desc()).limit(20)
    ).all()
    variant_count = len(session.scalars(select(ProductVariant)).all())
    sellable_count = len(
        session.scalars(
            select(ProductVariant).where(
                ProductVariant.active.is_(True),
                ProductVariant.sellable.is_(True),
            )
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        admin_context(
            request,
            actor,
            title="Admin | Black Metal Buddha",
            report=report,
            recent_orders=recent_orders,
            variant_count=variant_count,
            sellable_count=sellable_count,
            message=request.query_params.get("message"),
        ),
    )


@router.get("/orders")
def orders(
    request: Request,
    state: str | None = None,
    q: str | None = None,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    query = select(Order).order_by(Order.created_at.desc())
    if state:
        query = query.where(Order.order_state == state)
    if q:
        query = query.where(Order.order_number.contains(q.strip().upper()))
    rows = session.scalars(query.limit(200)).all()
    states = sorted(
        set(
            session.scalars(select(Order.order_state).distinct()).all()
        )
    )
    return templates.TemplateResponse(
        request,
        "admin/orders.html",
        admin_context(
            request,
            actor,
            title="Orders | Black Metal Buddha Admin",
            orders=rows,
            states=states,
            selected_state=state or "",
            search=q or "",
        ),
    )


@router.get("/orders/{order_number}")
def order_detail(
    request: Request,
    order_number: str,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    order = get_order_or_404(session, order_number)
    jobs = session.scalars(
        select(Job).where(Job.order_id == order.id).order_by(Job.created_at)
    ).all()
    refunds = session.scalars(
        select(Refund).where(Refund.order_id == order.id).order_by(Refund.created_at)
    ).all()
    payment_events = session.scalars(
        select(PaymentEvent)
        .where(PaymentEvent.provider_payment_id.in_([value for value in
            [order.square_payment_id, order.paypal_order_id, order.paypal_capture_id]
            + [refund.paypal_refund_id for refund in refunds] if value]))
        .order_by(PaymentEvent.processed_at.desc())
    ).all() if order.square_payment_id or order.paypal_order_id else []
    fulfillment_events = session.scalars(
        select(FulfillmentEvent)
        .where(FulfillmentEvent.provider_order_id == order.printful_order_id)
        .order_by(FulfillmentEvent.processed_at.desc())
    ).all() if order.printful_order_id else []
    audits = session.scalars(
        select(AuditLog)
        .where(AuditLog.object_type == "order", AuditLog.object_id == order.order_number)
        .order_by(AuditLog.created_at.desc())
    ).all()

    return templates.TemplateResponse(
        request,
        "admin/order_detail.html",
        admin_context(
            request,
            actor,
            title=f"{order.order_number} | Black Metal Buddha Admin",
            order=order,
            jobs=jobs,
            refunds=refunds,
            payment_events=payment_events,
            fulfillment_events=fulfillment_events,
            audits=audits,
            token_reconcile=csrf_token("reconcile", order.order_number),
            token_retry=csrf_token("retry_jobs", order.order_number),
            token_refund=csrf_token("refund", order.order_number),
            token_cancel=csrf_token("cancel_printful", order.order_number),
            message=request.query_params.get("message"),
        ),
    )


@router.post("/orders/{order_number}/reconcile")
async def reconcile_order_action(
    request: Request,
    order_number: str,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "reconcile", order_number)
    order = get_order_or_404(session, order_number)

    results: dict[str, str] = {}
    try:
        if order.payment_provider == "paypal" and order.paypal_order_id:
            with PayPalClient(settings) as provider:
                results["paypal"] = capture_paypal_order(session, order, client=provider, config=settings)
        elif order.square_order_id and settings.square_access_token:
            results["square"] = reconcile_square_order(session, order, client=SquareClient())
        if order.payment_state == "COMPLETED" and settings.printful_token and settings.printful_mode != "disabled":
            results["printful"] = reconcile_printful_order(session, order, client=PrintfulClient())
        if not results:
            results["providers"] = "No configured provider state to reconcile"
        record_audit(
            session,
            actor=actor,
            action="reconcile_order",
            object_type="order",
            object_id=order.order_number,
            details=results,
        )
        return redirect(f"/admin/orders/{order_number}", "Reconciliation completed.")
    except Exception as exc:
        session.rollback()
        record_audit(
            session,
            actor=actor,
            action="reconcile_order_failed",
            object_type="order",
            object_id=order.order_number,
            details={"error_type": type(exc).__name__},
        )
        return redirect(f"/admin/orders/{order_number}", f"Reconciliation failed: {type(exc).__name__}")


@router.post("/orders/{order_number}/retry-jobs")
async def retry_jobs_action(
    request: Request,
    order_number: str,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "retry_jobs", order_number)
    order = get_order_or_404(session, order_number)
    jobs = session.scalars(
        select(Job).where(Job.order_id == order.id, Job.state == "FAILED")
    ).all()
    for job in jobs:
        job.state = "PENDING"
        job.attempt_count = 0
        job.next_attempt_at = datetime.now(timezone.utc)
        job.last_error = None
    session.commit()
    record_audit(
        session,
        actor=actor,
        action="retry_failed_jobs",
        object_type="order",
        object_id=order.order_number,
        details={"count": len(jobs)},
    )
    return redirect(f"/admin/orders/{order_number}", f"Queued {len(jobs)} failed job(s) for retry.")


@router.post("/orders/{order_number}/refund")
async def refund_action(
    request: Request,
    order_number: str,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    if not settings.admin_refunds_enabled:
        raise HTTPException(status_code=403, detail="Admin refunds are disabled")

    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "refund", order_number)
    order = get_order_or_404(session, order_number)
    raw_amount = str(form.get("amount") or "").strip()
    try:
        amount_cents = money_to_cents(raw_amount) if raw_amount else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reason = str(form.get("reason") or "Customer refund").strip()[:192]

    try:
        refund = request_refund(
            session,
            order,
            amount_cents=amount_cents,
            reason=reason,
            client=PayPalClient(settings) if order.payment_provider == "paypal" else SquareClient(),
        )
        record_audit(
            session,
            actor=actor,
            action="request_refund",
            object_type="order",
            object_id=order.order_number,
            details={
                "refund_id": refund.paypal_refund_id or refund.square_refund_id,
                "amount_cents": refund.amount_cents,
                "status": refund.status,
            },
        )
        return redirect(f"/admin/orders/{order_number}", f"Refund {refund.status.lower()}.")
    except Exception as exc:
        session.rollback()
        unresolved = session.scalar(select(Refund.id).where(
            Refund.order_id == order.id, Refund.status == "REQUESTED",
            Refund.square_refund_id.is_(None), Refund.paypal_refund_id.is_(None)))
        record_audit(
            session,
            actor=actor,
            action="request_refund_pending" if unresolved is not None else "request_refund_failed",
            object_type="order",
            object_id=order.order_number,
            details={"error_type": type(exc).__name__},
        )
        if unresolved is not None:
            message = "Refund request recorded; awaiting confirmation. Retrying uses the same request."
        elif isinstance(exc, RefundError):
            message = str(exc)
        else:
            message = f"Refund failed: {type(exc).__name__}"
        return redirect(f"/admin/orders/{order_number}", message)


@router.post("/orders/{order_number}/cancel-printful")
async def cancel_printful_action(
    request: Request,
    order_number: str,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    if not settings.admin_cancel_fulfillment_enabled:
        raise HTTPException(status_code=403, detail="Printful cancellation is disabled")

    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "cancel_printful", order_number)
    order = get_order_or_404(session, order_number)
    if not order.printful_external_id:
        raise HTTPException(status_code=409, detail="Order has no Printful external ID")

    try:
        result = PrintfulClient().cancel_order(f"@{order.printful_external_id}")
        provider_status = str(result.get("status") or "canceled").upper()
        order.fulfillment_state = provider_status
        if provider_status == "CANCELED":
            order.order_state = "CANCELED"
        session.commit()
        record_audit(
            session,
            actor=actor,
            action="cancel_printful",
            object_type="order",
            object_id=order.order_number,
            details={"provider_status": provider_status},
        )
        return redirect(f"/admin/orders/{order_number}", f"Printful status: {provider_status}.")
    except Exception as exc:
        session.rollback()
        record_audit(
            session,
            actor=actor,
            action="cancel_printful_failed",
            object_type="order",
            object_id=order.order_number,
            details={"error_type": type(exc).__name__},
        )
        return redirect(f"/admin/orders/{order_number}", f"Cancellation failed: {type(exc).__name__}")


@router.get("/catalog")
def catalog(
    request: Request,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    variants = session.scalars(
        select(ProductVariant).order_by(
            ProductVariant.product_slug,
            ProductVariant.color,
            ProductVariant.size,
            ProductVariant.sku,
        )
    ).all()
    return templates.TemplateResponse(
        request,
        "admin/catalog.html",
        admin_context(
            request,
            actor,
            title="Catalog | Black Metal Buddha Admin",
            variants=variants,
            products=products_by_slug(session),
            token_new=csrf_token("create_variant", "new"),
            token_edit={item.id: csrf_token("edit_variant", str(item.id)) for item in variants},
            message=request.query_params.get("message"),
        ),
    )


def variant_values(form) -> dict:
    price = money_to_cents(str(form.get("price") or "0"))
    values = {
        "size": str(form.get("size") or "").strip().upper()[:32],
        "color": str(form.get("color") or "Black").strip()[:64],
        "retail_price_cents": price,
        "printful_product_id": str(form.get("printful_product_id") or "").strip() or None,
        "printful_variant_id": str(form.get("printful_variant_id") or "").strip() or None,
        "active": checkbox(form, "active"),
        "sellable": checkbox(form, "sellable"),
    }
    if not values["size"]:
        raise ValueError("Size is required")
    if values["sellable"]:
        if price <= 0:
            raise ValueError("Sellable variants require a positive price")
        if not values["printful_product_id"] or not values["printful_variant_id"]:
            raise ValueError("Sellable variants require both Printful IDs")
        if not values["active"]:
            raise ValueError("Sellable variants must also be active")
    return values


@router.post("/catalog/new")
async def create_variant_action(
    request: Request,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    require_catalog_writable()
    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "create_variant", "new")
    product_slug = str(form.get("product_slug") or "").strip()
    sku = str(form.get("sku") or "").strip().upper()[:128]
    if product_slug not in products_by_slug(session):
        return redirect("/admin/catalog", "Unknown product.")
    if not sku:
        return redirect("/admin/catalog", "SKU is required.")
    if session.scalar(select(ProductVariant).where(ProductVariant.sku == sku)):
        return redirect("/admin/catalog", "SKU already exists.")

    try:
        values = variant_values(form)
    except ValueError as exc:
        return redirect("/admin/catalog", str(exc))

    variant = ProductVariant(
        product_slug=product_slug,
        sku=sku,
        currency="USD",
        **values,
    )
    session.add(variant)
    session.commit()
    record_audit(
        session,
        actor=actor,
        action="create_variant",
        object_type="variant",
        object_id=sku,
        details={
            "product_slug": product_slug,
            "price_cents": variant.retail_price_cents,
            "active": variant.active,
            "sellable": variant.sellable,
        },
    )
    return redirect("/admin/catalog", f"Created {sku}.")


@router.post("/catalog/{variant_id}")
async def edit_variant_action(
    request: Request,
    variant_id: int,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    require_catalog_writable()
    form = await request.form()
    verify_csrf(str(form.get("csrf") or ""), "edit_variant", str(variant_id))
    variant = session.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")

    try:
        values = variant_values(form)
    except ValueError as exc:
        return redirect("/admin/catalog", str(exc))

    before = {
        "price_cents": variant.retail_price_cents,
        "active": variant.active,
        "sellable": variant.sellable,
        "printful_product_id": variant.printful_product_id,
        "printful_variant_id": variant.printful_variant_id,
    }
    for key, value in values.items():
        setattr(variant, key, value)
    session.commit()
    record_audit(
        session,
        actor=actor,
        action="edit_variant",
        object_type="variant",
        object_id=variant.sku,
        details={
            "before": before,
            "after": {
                "price_cents": variant.retail_price_cents,
                "active": variant.active,
                "sellable": variant.sellable,
                "printful_product_id": variant.printful_product_id,
                "printful_variant_id": variant.printful_variant_id,
            },
        },
    )
    return redirect("/admin/catalog", f"Updated {variant.sku}.")


@router.get("/audit")
def audit_log(
    request: Request,
    actor: str = Depends(require_admin),
    session: Session = Depends(db_session),
):
    entries = session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(250)
    ).all()
    return templates.TemplateResponse(
        request,
        "admin/audit.html",
        admin_context(
            request,
            actor,
            title="Audit Log | Black Metal Buddha Admin",
            entries=entries,
        ),
    )
