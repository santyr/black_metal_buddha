from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog import get_product
from .models import Job, Order, OrderItem, ProductVariant
from .schemas import CreateOrderIn
from .settings import settings


class OrderError(ValueError):
    pass


def verify_order_access(order: Order, token: str | None) -> None:
    if not isinstance(token, str) or not 16 <= len(token) <= 128 or not order.order_access_token_hash:
        raise OrderError("Order access token required")
    actual = hashlib.sha256(token.encode()).hexdigest()
    if not hmac.compare_digest(actual, order.order_access_token_hash):
        raise OrderError("Order access token required")


def new_order_number() -> str:
    return f"BMB-{uuid4().hex[:20].upper()}"


def recalculate_total(order: Order) -> None:
    order.total_cents = (
        order.subtotal_cents
        - order.discount_cents
        + order.shipping_cents
        + order.tax_cents
    )


def enqueue_job(session: Session, order: Order, job_type: str) -> bool:
    existing = session.scalar(
        select(Job).where(Job.order_id == order.id, Job.job_type == job_type)
    )
    if existing is not None:
        return False
    session.add(Job(job_type=job_type, order_id=order.id, state="PENDING"))
    return True


def create_order(session: Session, data: CreateOrderIn, *, is_canary: bool = False) -> Order:
    from .printful_catalog import CatalogSyncError, require_current_catalog
    try:
        require_current_catalog(session)
    except CatalogSyncError as exc:
        raise OrderError(str(exc)) from None
    order_id = str(uuid4())
    access_token = secrets.token_urlsafe(32)
    order_number = new_order_number()
    items: list[OrderItem] = []
    subtotal = 0
    currency: str | None = None

    for line in data.items:
        variant = session.scalar(
            select(ProductVariant).where(
                ProductVariant.sku == line.sku,
                ProductVariant.active.is_(True),
                ProductVariant.sellable.is_(True),
            )
        )
        if variant is None or variant.retail_price_cents is None:
            raise OrderError(f"SKU is not currently sellable: {line.sku}")
        if ((settings.printful_catalog_sync_enabled or line.printful_variant_id) and
                line.printful_variant_id != variant.printful_variant_id):
            raise OrderError("A product selection changed; refresh your cart and select the size again")

        product = get_product(variant.product_slug, session)
        if product is None:
            raise OrderError(f"Unknown product for SKU: {line.sku}")

        if currency is None:
            currency = variant.currency
        if currency != variant.currency:
            raise OrderError("Mixed-currency orders are not supported")

        line_total = variant.retail_price_cents * line.quantity
        subtotal += line_total
        items.append(
            OrderItem(
                order_id=order_id,
                product_variant_id=variant.id,
                sku_snapshot=variant.sku,
                name_snapshot=product.name,
                size_snapshot=variant.size,
                color_snapshot=variant.color,
                unit_price_cents=variant.retail_price_cents,
                quantity=line.quantity,
                line_total_cents=line_total,
                printful_product_id_snapshot=variant.printful_product_id,
                printful_variant_id_snapshot=variant.printful_variant_id,
            )
        )

    order = Order(
        id=order_id,
        order_access_token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
        order_number=order_number,
        email=str(data.recipient.email),
        customer_name=data.recipient.name,
        phone=data.recipient.phone,
        ship_address1=data.recipient.address1,
        ship_address2=data.recipient.address2,
        ship_city=data.recipient.city,
        ship_state=data.recipient.state,
        ship_postal_code=data.recipient.postal_code,
        ship_country=data.recipient.country_code.upper(),
        currency=currency or "USD",
        subtotal_cents=subtotal,
        discount_cents=0,
        shipping_cents=0,
        tax_cents=0,
        total_cents=subtotal,
        printful_external_id=order_number,
        is_canary=is_canary,
        items=items,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    order._plain_order_token = access_token
    return order


def validate_pending_catalog(session: Session, order: Order) -> None:
    if not settings.printful_catalog_sync_enabled:
        return
    from .printful_catalog import CatalogSyncError, require_current_catalog
    try:
        require_current_catalog(session)
    except CatalogSyncError as exc:
        raise OrderError(str(exc)) from None
    for item in order.items:
        variant = session.get(ProductVariant, item.product_variant_id)
        if (variant is None or not variant.active or not variant.sellable or
                variant.printful_product_id != item.printful_product_id_snapshot or
                variant.printful_variant_id != item.printful_variant_id_snapshot or
                variant.retail_price_cents != item.unit_price_cents or
                variant.currency != order.currency or variant.size != item.size_snapshot or
                variant.color != item.color_snapshot):
            raise OrderError("A product selection changed; return to your cart and start checkout again")


def get_order(session: Session, order_number: str) -> Order | None:
    return session.scalar(select(Order).where(Order.order_number == order_number))


def get_order_by_square_order_id(session: Session, square_order_id: str) -> Order | None:
    return session.scalar(select(Order).where(Order.square_order_id == square_order_id))


def shipping_quote_is_fresh(order: Order, *, max_age_minutes: int = 15) -> bool:
    if not order.shipping_method or order.shipping_quoted_at is None:
        return False
    quoted_at = order.shipping_quoted_at
    if quoted_at.tzinfo is None:
        quoted_at = quoted_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - quoted_at
    return age.total_seconds() <= max_age_minutes * 60


def set_shipping_rate(
    session: Session,
    order: Order,
    *,
    shipping_method: str,
    shipping_cents: int,
    currency: str,
) -> None:
    session.execute(update(Order).where(Order.id == order.id).values(id=Order.id))
    session.refresh(order)
    if order.square_payment_link_id or order.paypal_create_request_id:
        raise OrderError("Shipping cannot change after payment checkout is created")
    if currency != order.currency:
        raise OrderError("Shipping quote currency mismatch")
    if shipping_cents < 0:
        raise OrderError("Shipping cannot be negative")
    order.shipping_method = shipping_method
    order.shipping_cents = shipping_cents
    order.shipping_quoted_at = datetime.now(timezone.utc)
    recalculate_total(order)
    session.commit()


def sync_square_pricing(
    session: Session,
    order: Order,
    square_order: dict,
) -> None:
    if square_order.get("reference_id") != order.order_number:
        raise OrderError("Square order reference mismatch")

    line_items = square_order.get("line_items") or []
    if len(line_items) != len(order.items):
        raise OrderError("Square line-item count mismatch")

    expected_lines = sorted(
        (item.name_snapshot, str(item.quantity), item.unit_price_cents)
        for item in order.items
    )
    actual_lines = sorted(
        (
            str(line.get("name") or ""),
            str(line.get("quantity") or ""),
            int((line.get("base_price_money") or {}).get("amount", -1)),
        )
        for line in line_items
    )
    if expected_lines != actual_lines:
        raise OrderError("Square line-item pricing mismatch")

    total_service = square_order.get("total_service_charge_money") or {}
    if int(total_service.get("amount", 0)) != order.shipping_cents:
        raise OrderError("Square shipping/service-charge mismatch")
    if total_service and total_service.get("currency") not in {None, order.currency}:
        raise OrderError("Square shipping currency mismatch")

    total_discount = square_order.get("total_discount_money") or {}
    if int(total_discount.get("amount", 0)) != order.discount_cents:
        raise OrderError("Square discount mismatch")

    tax_money = square_order.get("total_tax_money") or {}
    total_money = square_order.get("total_money") or {}
    if tax_money.get("currency") not in {None, order.currency}:
        raise OrderError("Square tax currency mismatch")
    if total_money.get("currency") != order.currency:
        raise OrderError("Square total currency mismatch")

    tax_cents = int(tax_money.get("amount", 0))
    total_cents = int(total_money.get("amount", -1))
    expected_total = (
        order.subtotal_cents
        - order.discount_cents
        + order.shipping_cents
        + tax_cents
    )
    if total_cents != expected_total:
        raise OrderError("Square calculated total is inconsistent")

    order.tax_cents = tax_cents
    order.total_cents = total_cents
    session.commit()


def set_square_checkout(
    session: Session,
    order: Order,
    *,
    payment_link_id: str,
    square_order_id: str,
    checkout_url: str,
) -> None:
    if order.order_state != "PENDING_PAYMENT":
        raise OrderError("Square checkout can only be attached to a pending order")
    order.square_payment_link_id = payment_link_id
    order.square_order_id = square_order_id
    order.square_checkout_url = checkout_url
    session.commit()


def mark_paid_and_enqueue(
    session: Session,
    order: Order,
    *,
    square_payment_id: str,
) -> bool:
    if order.payment_state == "COMPLETED":
        return False

    order.payment_state = "COMPLETED"
    order.order_state = "PAID"
    order.square_payment_id = square_payment_id
    order.paid_at = datetime.now(timezone.utc)
    enqueue_job(session, order, "SUBMIT_PRINTFUL_ORDER")
    enqueue_job(session, order, "SEND_ORDER_CONFIRMATION")

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        current = get_order(session, order.order_number)
        if current is not None and current.payment_state == "COMPLETED":
            return False
        raise
    return True
