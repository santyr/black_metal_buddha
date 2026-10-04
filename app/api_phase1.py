from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import SessionLocal
from .fulfillment.printful import PrintfulClient, verify_printful_webhook
from .models import FulfillmentEvent, Order, PaymentEvent, Refund, Job
from .orders import (
    OrderError,
    create_order,
    enqueue_job,
    get_order,
    get_order_by_square_order_id,
    mark_paid_and_enqueue,
    set_shipping_rate,
    set_square_checkout,
    shipping_quote_is_fresh,
    sync_square_pricing,
    validate_pending_catalog,
    verify_order_access,
)
from .payments.square import SquareClient, verify_square_webhook
from .payments.paypal import PayPalClient, PayPalAPIError, PayPalConfigurationError
from .payments.paypal_checkout import prepare_paypal_checkout, lock_order
from .payments.paypal_capture import capture_paypal_order
from .tax import TaxConfigurationError
from .rate_limit import limiter
from .refunds import apply_refund_status, get_refund_by_square_id
from .schemas import CatalogVariantOut, CreateOrderIn, OrderOut, SelectShippingIn, ShippingRateOut
from .settings import settings
from .storefront import sellable_catalog
from .shipments import upsert_printful_shipment

router = APIRouter(prefix="/api/v1", tags=["phase1"])
paypal_router = APIRouter(prefix="/api/phase1", tags=["paypal"])


def _object(value, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"Invalid {name} object")
    return value


def _webhook_event(body: bytes) -> dict:
    try:
        event = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    if not isinstance(event, dict) or not isinstance(event.get("type", ""), str):
        raise HTTPException(status_code=400, detail="Invalid webhook event")
    return event


def _store_event(session: Session, event: PaymentEvent | FulfillmentEvent) -> bool:
    model = type(event)
    provider, event_id = event.provider, event.provider_event_id
    session.add(event)
    try:
        session.commit()
        return False
    except IntegrityError:
        session.rollback()
        if session.scalar(select(model).where(model.provider == provider,
                                               model.provider_event_id == event_id)) is not None:
            return True
        raise


def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _require_phase1() -> None:
    if not settings.phase1_api_enabled:
        raise HTTPException(status_code=503, detail="Phase 1 API is disabled")


def _client_identity(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _limit_customer_mutation(
    request: Request,
    *,
    bucket: str,
    limit: int = 30,
    window_seconds: int = 600,
) -> None:
    if not limiter.allow(
        bucket=bucket,
        identity=_client_identity(request),
        limit=limit,
        window_seconds=window_seconds,
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many checkout requests. Please wait and try again.",
            headers={"Retry-After": str(window_seconds)},
        )

    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.public_base_url:
        raise HTTPException(status_code=403, detail="Cross-origin checkout request rejected")


def _get_order_or_404(session: Session, order_number: str) -> Order:
    order = get_order(session, order_number)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _order_out(order: Order, checkout_url: str | None = None, *, order_token: str | None = None) -> OrderOut:
    return OrderOut(
        order_number=order.order_number,
        order_state=order.order_state,
        payment_state=order.payment_state,
        fulfillment_state=order.fulfillment_state,
        currency=order.currency,
        subtotal_cents=order.subtotal_cents,
        discount_cents=order.discount_cents,
        shipping_cents=order.shipping_cents,
        shipping_method=order.shipping_method,
        tax_cents=order.tax_cents,
        total_cents=order.total_cents,
        refunded_cents=order.refunded_cents,
        refund_state=order.refund_state,
        square_checkout_url=checkout_url or order.square_checkout_url,
        checkout_url=order.paypal_checkout_url or checkout_url or order.square_checkout_url,
        order_token=order_token,
    )


@router.get("/catalog", response_model=list[CatalogVariantOut])
def api_catalog(session: Session = Depends(db_session)):
    _require_phase1()
    return [
        CatalogVariantOut(
            sku=item.sku,
            product_slug=item.product_slug,
            product_name=item.product_name,
            size=item.size,
            color=item.color,
            currency=item.currency,
            retail_price_cents=item.retail_price_cents,
        )
        for item in sellable_catalog(session)
    ]


@router.post("/orders", response_model=OrderOut)
def api_create_order(
    data: CreateOrderIn,
    request: Request,
    session: Session = Depends(db_session),
):
    _require_phase1()
    _limit_customer_mutation(request, bucket="create-order", limit=15)
    try:
        order = create_order(session, data)
    except OrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _order_out(order, order_token=getattr(order, "_plain_order_token", None))


@router.get("/orders/{order_number}", response_model=OrderOut)
def api_get_order(order_number: str, session: Session = Depends(db_session)):
    _require_phase1()
    return _order_out(_get_order_or_404(session, order_number))


@router.get(
    "/orders/{order_number}/shipping-rates",
    response_model=list[ShippingRateOut],
)
def api_shipping_rates(
    order_number: str,
    request: Request,
    session: Session = Depends(db_session),
):
    _require_phase1()
    _limit_customer_mutation(request, bucket="shipping-rates", limit=60)
    order = _get_order_or_404(session, order_number)
    _require_order_token(request, order, allow_legacy=True)
    if order.square_payment_link_id or order.paypal_create_request_id:
        raise HTTPException(status_code=409, detail="Checkout already created")

    try:
        rates = PrintfulClient().get_shipping_rates(order)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to quote shipping") from exc

    return [ShippingRateOut(**rate) for rate in rates]


@router.post("/orders/{order_number}/shipping", response_model=OrderOut)
def api_select_shipping(
    order_number: str,
    data: SelectShippingIn,
    request: Request,
    session: Session = Depends(db_session),
):
    _require_phase1()
    _limit_customer_mutation(request, bucket="select-shipping", limit=30)
    order = _get_order_or_404(session, order_number)
    _require_order_token(request, order, allow_legacy=True)
    if order.square_payment_link_id or order.paypal_create_request_id:
        raise HTTPException(status_code=409, detail="Checkout already created")

    try:
        rates = PrintfulClient().get_shipping_rates(order)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to quote shipping") from exc

    selected = next((rate for rate in rates if rate["shipping"] == data.shipping), None)
    if selected is None:
        raise HTTPException(status_code=400, detail="Shipping method is not currently available")

    try:
        set_shipping_rate(
            session,
            order,
            shipping_method=selected["shipping"],
            shipping_cents=selected["rate_cents"],
            currency=selected["currency"],
        )
    except OrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _order_out(order)


@router.post("/orders/{order_number}/square-checkout", response_model=OrderOut)
def api_square_checkout(
    order_number: str,
    request: Request,
    session: Session = Depends(db_session),
):
    _require_phase1()
    _limit_customer_mutation(request, bucket="square-checkout", limit=20)
    order = _get_order_or_404(session, order_number)
    _require_order_token(request, order, allow_legacy=True)
    if order.paypal_create_request_id or order.payment_provider == "paypal":
        raise HTTPException(status_code=409, detail="PayPal checkout already created")
    if order.square_payment_link_id:
        return _order_out(order, order.square_checkout_url)
    if not shipping_quote_is_fresh(order):
        raise HTTPException(status_code=409, detail="Shipping quote is missing or expired")
    try:
        validate_pending_catalog(session, order)
    except OrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    client = SquareClient()
    try:
        payment_link = client.create_payment_link(order)
        square_order = client.get_order(payment_link["order_id"])
        sync_square_pricing(session, order, square_order)
        set_square_checkout(
            session,
            order,
            payment_link_id=payment_link["id"],
            square_order_id=payment_link["order_id"],
            checkout_url=payment_link["url"],
        )
    except OrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to create Square checkout") from exc

    return _order_out(order, payment_link["url"])


def _require_order_token(request: Request, order: Order, *, allow_legacy: bool = False) -> None:
    if allow_legacy and order.order_access_token_hash is None:
        return
    try:
        verify_order_access(order, request.headers.get("x-bmb-order-token"))
    except OrderError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


def _require_paypal_checkout() -> None:
    _require_phase1()
    if settings.app_env == "production" and not settings.paypal_production_canary_approved:
        raise HTTPException(status_code=503, detail="PayPal launch verification is incomplete")


@paypal_router.post("/orders/{order_number}/paypal-checkout", response_model=OrderOut)
def api_paypal_checkout(order_number: str, request: Request, session: Session = Depends(db_session)):
    _require_paypal_checkout()
    _limit_customer_mutation(request, bucket="paypal-checkout", limit=20)
    order = _get_order_or_404(session, order_number)
    _require_order_token(request, order)
    try:
        prepare_paypal_checkout(session, order, config=settings)
    except OrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except (TaxConfigurationError, PayPalConfigurationError):
        raise HTTPException(status_code=503, detail="Checkout configuration is incomplete") from None
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to prepare PayPal checkout; retry this order") from None
    return _order_out(order)


@paypal_router.post("/orders/{order_number}/paypal-capture", response_model=OrderOut)
def api_paypal_capture(order_number: str, request: Request, session: Session = Depends(db_session)):
    _require_paypal_checkout()
    _limit_customer_mutation(request, bucket="paypal-capture", limit=30)
    order = _get_order_or_404(session, order_number)
    _require_order_token(request, order)
    try:
        capture_paypal_order(session, order, config=settings)
    except OrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PayPalConfigurationError:
        raise HTTPException(status_code=503, detail="Payment configuration is incomplete") from None
    except Exception:
        raise HTTPException(status_code=502, detail="Payment confirmation is pending; retry this order") from None
    return _order_out(order)


@paypal_router.post("/webhooks/paypal", include_in_schema=False)
async def paypal_webhook(request: Request, session: Session = Depends(db_session)):
    # Existing payments remain recoverable while public checkout is disabled.
    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(status_code=413, detail="Webhook body is too large")
    try:
        event = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from None
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook event")
    event_id, kind = event.get('id'), event.get('event_type')
    if (not isinstance(event_id, str) or not 1 <= len(event_id) <= 128
            or not isinstance(kind, str) or not 1 <= len(kind) <= 128):
        raise HTTPException(status_code=400, detail="Invalid PayPal event identity")
    provider = PayPalClient(settings)
    try:
        verified = provider.verify_webhook(dict(request.headers), event)
    except (PayPalAPIError, PayPalConfigurationError):
        raise HTTPException(status_code=503, detail="PayPal verification is temporarily unavailable") from None
    finally:
        provider.close()
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid PayPal signature")
    resource = _object(event.get('resource'), 'resource')
    order_id = None
    capture_events = {'PAYMENT.CAPTURE.COMPLETED', 'PAYMENT.CAPTURE.PENDING', 'PAYMENT.CAPTURE.DECLINED',
                      'PAYMENT.CAPTURE.REVERSED'}
    refund_events = {'PAYMENT.CAPTURE.REFUNDED', 'PAYMENT.REFUND.PENDING', 'PAYMENT.REFUND.FAILED'}
    refund_data = None
    if kind == 'CHECKOUT.ORDER.APPROVED':
        order_id = resource.get('id')
    elif kind in capture_events:
        related = _object(_object(resource.get('supplementary_data'), 'supplementary_data').get('related_ids'), 'related_ids')
        order_id = related.get('order_id')
    elif kind in refund_events:
        refund_id = resource.get('id')
        if not isinstance(refund_id, str) or not 1 <= len(refund_id) <= 128:
            raise HTTPException(status_code=400, detail="Invalid PayPal refund identity")
        lookup = PayPalClient(settings)
        try:
            refund_data = lookup.get_refund(refund_id)
            if refund_data.get('id') != refund_id:
                raise HTTPException(status_code=409, detail="PayPal refund identity mismatch")
            prefix = settings.paypal_api_base + '/v2/payments/captures/'
            up = next((link.get('href') for link in refund_data.get('links', [])
                       if isinstance(link, dict) and link.get('rel') == 'up'), None)
            if not isinstance(up, str) or not up.startswith(prefix):
                raise HTTPException(status_code=409, detail="PayPal refund capture relationship missing")
            capture = lookup.get_capture(up[len(prefix):])
            related = _object(_object(capture.get('supplementary_data'), 'supplementary_data').get('related_ids'), 'related_ids')
            order_id = related.get('order_id')
        except (PayPalAPIError, PayPalConfigurationError):
            raise HTTPException(status_code=503, detail="PayPal refund lookup is temporarily unavailable") from None
        finally:
            lookup.close()
    if order_id is not None and (not isinstance(order_id, str) or not 1 <= len(order_id) <= 128):
        raise HTTPException(status_code=400, detail="Invalid PayPal order identity")
    order = session.scalar(select(Order).where(Order.paypal_order_id == order_id)) if order_id else None
    if order is None and kind in capture_events and isinstance(resource.get('id'), str):
        # Capture callbacks can omit related_ids, and can outrun our POST response.
        # Resolve the relationship via a fixed API endpoint, never a webhook URL.
        lookup = PayPalClient(settings)
        try:
            capture = lookup.get_capture(resource['id'])
            if capture.get('id') != resource['id']:
                raise HTTPException(status_code=409, detail="PayPal capture identity mismatch")
            related = _object(_object(capture.get('supplementary_data'), 'supplementary_data').get('related_ids'), 'related_ids')
            resolved = related.get('order_id')
            order = session.scalar(select(Order).where(Order.paypal_order_id == resolved)) if isinstance(resolved, str) else None
        except (PayPalAPIError, PayPalConfigurationError):
            raise HTTPException(status_code=503, detail="PayPal capture lookup is temporarily unavailable") from None
        finally:
            lookup.close()
    if order is not None:
        lock_order(session, order)
    existing = session.scalar(select(PaymentEvent).where(PaymentEvent.provider == 'paypal',
                                                       PaymentEvent.provider_event_id == event_id))
    if existing:
        session.rollback()
        return {'ok':True, 'duplicate':True}
    result = 'IGNORED'
    if order is not None and order.payment_provider == 'paypal':
        enqueue_job(session, order, 'CAPTURE_PAYPAL_ORDER')
        job = session.scalar(select(Job).where(Job.order_id == order.id, Job.job_type == 'CAPTURE_PAYPAL_ORDER'))
        if job is not None and job.state != 'RUNNING':
            job.state = 'PENDING'
            job.next_attempt_at = datetime.now(timezone.utc)
            job.last_error = None
            job.attempt_count = 0
        result = 'REVERSAL_QUEUED' if kind == 'PAYMENT.CAPTURE.REVERSED' else 'CAPTURE_QUEUED'
        if refund_data is not None:
            from .payments.paypal import decimal_to_cents
            amount = _object(refund_data.get('amount'), 'refund amount')
            try:
                cents = decimal_to_cents(amount.get('value'))
            except ValueError:
                raise HTTPException(status_code=409, detail="Invalid PayPal refund amount") from None
            if amount.get('currency_code') != order.currency or not 0 < cents <= order.total_cents:
                raise HTTPException(status_code=409, detail="PayPal refund amount/currency mismatch")
            refund = session.scalar(select(Refund).where(Refund.paypal_refund_id == refund_data['id']))
            if refund is None and isinstance(refund_data.get('custom_id'), str):
                refund = session.scalar(select(Refund).where(Refund.paypal_request_id == refund_data['custom_id']))
            if refund is None:
                unresolved = session.scalar(select(Refund.id).where(Refund.order_id == order.id,
                    Refund.status == 'REQUESTED', Refund.paypal_refund_id.is_(None)))
                if unresolved is not None:
                    raise HTTPException(status_code=503, detail="Refund request is still being resolved")
                refund = Refund(order_id=order.id, payment_provider='paypal', paypal_refund_id=refund_data['id'],
                                amount_cents=cents, currency=order.currency, status='PENDING', reason='PayPal dashboard refund')
                session.add(refund)
            elif (refund.order_id != order.id or refund.payment_provider != 'paypal'
                  or refund.amount_cents != cents or refund.currency != order.currency):
                raise HTTPException(status_code=409, detail="PayPal refund reservation mismatch")
            refund.paypal_refund_id = refund_data['id']
            if refund.status == 'REQUESTED':
                refund.status = 'PENDING'
            if refund.status not in {'COMPLETED', 'FAILED', 'REJECTED'}:
                order.refund_state = 'PENDING'
            session.flush()
            enqueue_job(session, order, f'RECONCILE_PAYPAL_REFUND:{refund.id}')
            result = 'REFUND_QUEUED'
    # Event + its durable job are committed together; duplicate races roll back both.
    duplicate = _store_event(session, PaymentEvent(provider='paypal', provider_event_id=event_id,
        provider_payment_id=resource.get('id') if isinstance(resource.get('id'), str) and len(resource['id']) <= 128 else None,
        event_type=kind, payload_hash=hashlib.sha256(body).hexdigest(), processing_result=result))
    return {'ok':True, 'result':result, 'duplicate':duplicate}


@router.post("/webhooks/square", include_in_schema=False)
async def square_webhook(request: Request, session: Session = Depends(db_session)):
    body = await request.body()
    signature = request.headers.get("x-square-hmacsha256-signature")
    if not verify_square_webhook(body, signature):
        raise HTTPException(status_code=401, detail="Invalid Square signature")

    event = _webhook_event(body)
    event_id = event.get("event_id") or event.get("id")
    event_type = event.get("type") or ""
    if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
        raise HTTPException(status_code=400, detail="Square event ID missing")

    existing = session.scalar(
        select(PaymentEvent).where(
            PaymentEvent.provider == "square",
            PaymentEvent.provider_event_id == event_id,
        )
    )
    if existing:
        return {"ok": True, "duplicate": True}

    obj = _object(_object(event.get("data"), "data").get("object"), "data.object")
    payment = _object(obj.get("payment"), "payment")
    refund_data = _object(obj.get("refund"), "refund")
    provider_payment_id = payment.get("id") or refund_data.get("payment_id")
    result = "IGNORED"

    if event_type in {"payment.created", "payment.updated"}:
        payment_id = payment.get("id")
        square_order_id = payment.get("order_id")
        status = str(payment.get("status") or "").upper()
        amount_money = _object(payment.get("amount_money"), "amount_money")

        if square_order_id:
            order = get_order_by_square_order_id(session, square_order_id)
            if order is not None:
                try:
                    square_order = SquareClient().get_order(square_order_id)
                    sync_square_pricing(session, order, square_order)
                except OrderError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc

                if amount_money.get("currency") != order.currency:
                    raise HTTPException(status_code=409, detail="Square currency mismatch")
                if type(amount_money.get("amount")) is not int:
                    raise HTTPException(status_code=400, detail="Invalid Square payment amount")
                if amount_money["amount"] != order.total_cents:
                    raise HTTPException(status_code=409, detail="Square amount mismatch")

                if status == "COMPLETED" and payment_id:
                    mark_paid_and_enqueue(session, order, square_payment_id=payment_id)
                    result = "PAID"
                elif status in {"FAILED", "CANCELED"} and order.payment_state != "COMPLETED":
                    order.payment_state = status
                    order.order_state = "PAYMENT_FAILED"
                    session.commit()
                    result = status
                else:
                    result = status or "PENDING"

    elif event_type in {"refund.created", "refund.updated"}:
        refund_id = refund_data.get("id")
        if not isinstance(refund_id, str) or not refund_id or len(refund_id) > 255:
            raise HTTPException(status_code=400, detail="Invalid Square refund ID")
        refund_status = refund_data.get("status")
        if not isinstance(refund_status, str) or refund_status not in {"PENDING", "COMPLETED", "REJECTED", "FAILED"}:
            raise HTTPException(status_code=400, detail="Invalid Square refund status")
        if refund_id:
            refund = get_refund_by_square_id(session, str(refund_id))
            if refund is None and refund_data.get("payment_id"):
                order = session.scalar(select(Order).where(
                    Order.square_payment_id == refund_data["payment_id"]))
                if order is not None:
                    unresolved = session.scalar(select(Refund.id).where(
                        Refund.order_id == order.id, Refund.status == "REQUESTED",
                        Refund.square_refund_id.is_(None)))
                    if unresolved is not None:
                        # A webhook can outrun the refund HTTP response. Do not
                        # guess which request it belongs to using only its amount.
                        raise HTTPException(status_code=503, detail="Refund request is still being resolved")
                    money = _object(refund_data.get("amount_money"), "refund amount_money")
                    if (type(money.get("amount")) is not int
                            or not 0 < money["amount"] <= order.total_cents
                            or money.get("currency") != order.currency):
                        raise HTTPException(status_code=409, detail="Square refund amount or currency mismatch")
                    refund = Refund(order_id=order.id, square_refund_id=str(refund_id),
                                    amount_cents=money["amount"], currency=order.currency,
                                    status="PENDING", reason=refund_data.get("reason"))
                    session.add(refund)
                    session.flush()
            if refund is not None:
                order = session.get(Order, refund.order_id)
                if order is not None:
                    if refund_data.get("payment_id") not in (None, order.square_payment_id):
                        raise HTTPException(status_code=409, detail="Square refund payment mismatch")
                    if refund_data.get("amount_money") is not None:
                        money = _object(refund_data["amount_money"], "refund amount_money")
                        if money.get("amount") != refund.amount_cents or money.get("currency") != refund.currency:
                            raise HTTPException(status_code=409, detail="Square refund amount or currency mismatch")
                    apply_refund_status(
                        session,
                        refund,
                        order,
                        status=str(refund_data.get("status") or refund.status),
                    )
                    result = refund.status

    event_time = None
    if isinstance(event.get("created_at"), str):
        try:
            event_time = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        except ValueError:
            event_time = None

    duplicate = _store_event(session,
        PaymentEvent(
            provider="square",
            provider_event_id=event_id,
            provider_payment_id=provider_payment_id,
            event_type=event_type,
            event_time=event_time,
            payload_hash=hashlib.sha256(body).hexdigest(),
            processing_result=result,
        )
    )
    return {"ok": True, "result": result, "duplicate": duplicate}


@router.post("/webhooks/printful", include_in_schema=False)
async def printful_webhook(request: Request, session: Session = Depends(db_session)):
    body = await request.body()
    signature = request.headers.get("x-pf-webhook-signature")
    public_key = request.headers.get("x-pf-webhook-public-key")

    if settings.printful_webhook_public_key and public_key != settings.printful_webhook_public_key:
        raise HTTPException(status_code=401, detail="Unexpected Printful public key")
    if not verify_printful_webhook(body, signature):
        raise HTTPException(status_code=401, detail="Invalid Printful signature")

    event = _webhook_event(body)
    event_type = event.get("type") or ""
    event_hash = hashlib.sha256(body).hexdigest()

    existing = session.scalar(
        select(FulfillmentEvent).where(
            FulfillmentEvent.provider == "printful",
            FulfillmentEvent.provider_event_id == event_hash,
        )
    )
    if existing:
        return {"ok": True, "duplicate": True}

    data = _object(event.get("data"), "data")
    pf_order = _object(data.get("order"), "order")
    external_id = pf_order.get("external_id")
    order = None
    if external_id:
        order = session.scalar(select(Order).where(Order.order_number == external_id))

    result = "IGNORED"
    if order is not None:
        pf_status = str(pf_order.get("status") or "").upper()
        if pf_order.get("id") is not None:
            order.printful_order_id = str(pf_order["id"])

        if event_type in {"order_created", "order_updated"}:
            order.fulfillment_state = pf_status or "DRAFT"
            if pf_status == "FULFILLED":
                order.order_state = "SHIPPED"
            elif pf_status == "PARTIAL":
                order.order_state = "PARTIALLY_SHIPPED"
            elif pf_status == "INPROCESS":
                order.order_state = "IN_PRODUCTION"
            elif order.order_state == "PAID":
                order.order_state = "FULFILLMENT_SUBMITTED"
            result = order.fulfillment_state
        elif event_type == "order_put_hold":
            order.fulfillment_state = "HOLD"
            order.order_state = "FULFILLMENT_HOLD"
            result = "HOLD"
        elif event_type == "order_failed":
            order.fulfillment_state = "FAILED"
            order.order_state = "FULFILLMENT_FAILED"
            result = "FAILED"
        elif event_type == "order_canceled":
            order.fulfillment_state = "CANCELED"
            result = "CANCELED"
        elif event_type in {"shipment_sent", "shipment_delivered", "shipment_returned"}:
            shipment = upsert_printful_shipment(
                session,
                order,
                _object(data.get("shipment"), "shipment"),
                event_type=event_type,
                printful_order_status=pf_order.get("status"),
            )
            if shipment is not None and event_type == "shipment_sent":
                order.shipped_at = order.shipped_at or shipment.shipped_at or datetime.now(timezone.utc)
            result = shipment.status if shipment is not None else "SHIPMENT_MISSING"

    duplicate = _store_event(session,
        FulfillmentEvent(
            provider="printful",
            provider_event_id=event_hash,
            provider_order_id=str(pf_order.get("id")) if pf_order.get("id") is not None else None,
            event_type=event_type,
            payload_hash=event_hash,
            processing_result=result,
        )
    )
    return {"ok": True, "result": result, "duplicate": duplicate}
