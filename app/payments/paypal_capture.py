"""One authoritative capture path for browser callbacks, jobs and reconciliation."""
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Order, PaymentEvent
from ..orders import OrderError, enqueue_job
from ..settings import Settings, settings
from .paypal import PayPalClient, decimal_to_cents
from .paypal_checkout import lock_order, validate_remote_order, validate_snapshot


def remote_capture_id(remote: dict) -> str | None:
    try:
        captures = remote['purchase_units'][0].get('payments', {}).get('captures', [])
        if not isinstance(captures, list) or len(captures) > 1:
            raise OrderError("PayPal order contains unexpected captures")
        if not captures:
            return None
        identity = captures[0]['id']
        if not isinstance(identity, str) or not identity:
            raise ValueError
        return identity
    except (KeyError, TypeError, IndexError, ValueError):
        raise OrderError("PayPal capture identity is invalid") from None


def apply_paypal_capture(session: Session, order: Order, capture: dict, *,
                         config: Settings = settings) -> bool:
    """Accept an internal envelope from trusted GET capture + GET order calls.

    `_paypal_order` is added locally, never taken from browser/webhook input.
    Validation and job insertion commit atomically under the order row lock.
    """
    try:
        lock_order(session, order)
        validate_snapshot(order, config)
        remote = capture['_paypal_order']
        validate_remote_order(order, remote, config)
        identity = capture['id']
        if (order.payment_provider != 'paypal' or not order.paypal_order_id
                or remote['id'] != order.paypal_order_id
                or remote_capture_id(remote) != identity
                or capture['supplementary_data']['related_ids']['order_id'] != order.paypal_order_id
                or capture['payee']['merchant_id'] != config.paypal_merchant_id
                or capture['amount']['currency_code'] != order.currency
                or decimal_to_cents(capture['amount']['value']) != order.total_cents
                or capture.get('final_capture') is not True
                or order.paypal_capture_id not in {None, identity}):
            raise OrderError("PayPal capture does not match the frozen checkout")
        status = capture['status']
        if status not in {'COMPLETED', 'PENDING', 'DECLINED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED'}:
            raise OrderError("PayPal capture status requires review")
        order.paypal_capture_id = identity
        order.paypal_capture_json = json.dumps({key:value for key,value in capture.items()
                                               if key != '_paypal_order'}, sort_keys=True, allow_nan=False)
        breakdown = capture.get('seller_receivable_breakdown') or {}
        for field, column in (('paypal_fee', 'paypal_fee_cents'), ('net_amount', 'paypal_net_cents')):
            money = breakdown.get(field) if isinstance(breakdown, dict) else None
            if isinstance(money, dict) and money.get('currency_code') == order.currency:
                try:
                    setattr(order, column, decimal_to_cents(money.get('value')))
                except ValueError:
                    pass  # Unknown receipt data never becomes an invented fee/net.
        newly_paid = status == 'COMPLETED' and order.payment_state != 'COMPLETED'
        if status == 'COMPLETED':
            if newly_paid:
                if order.payment_state not in {'PENDING', 'FAILED'} or order.refunded_cents:
                    raise OrderError("Payment state requires review")
                order.payment_state = 'COMPLETED'
                order.order_state = 'PAID'
                order.paid_at = datetime.now(timezone.utc)
            if order.refunded_cents < order.total_cents and order.refund_state != 'COMPLETED':
                enqueue_job(session, order, 'SUBMIT_PRINTFUL_ORDER')
                enqueue_job(session, order, 'SEND_ORDER_CONFIRMATION')
        elif status in {'DECLINED', 'FAILED'} and order.payment_state != 'COMPLETED':
            order.payment_state = 'FAILED'
            order.order_state = 'PAYMENT_FAILED'
        # PENDING and refunded provider records never newly fulfill or regress PAID.
        session.commit()
        return newly_paid
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        session.rollback()
        if isinstance(exc, OrderError):
            raise
        raise OrderError("PayPal capture does not match the frozen checkout") from None
    except Exception:
        session.rollback()
        raise


def capture_paypal_order(session: Session, order: Order, *, config: Settings = settings,
                         client: PayPalClient | None = None) -> str:
    provider = client or PayPalClient(config)
    try:
        validate_snapshot(order, config)
        if not order.paypal_order_id or order.payment_provider != 'paypal':
            raise OrderError("No PayPal order is attached")
        remote = provider.get_order(order.paypal_order_id)
        if remote.get('id') != order.paypal_order_id:
            raise OrderError("PayPal order identity mismatch")
        validate_remote_order(order, remote, config)
        identity = remote_capture_id(remote)
        if not identity:
            if remote.get('status') != 'APPROVED':
                if remote.get('status') not in {'CREATED', 'PAYER_ACTION_REQUIRED', 'VOIDED'}:
                    raise OrderError("PayPal order requires reconciliation")
                return remote['status']
            lock_order(session, order)
            validate_snapshot(order, config)
            if not order.paypal_capture_request_id:
                order.paypal_capture_request_id = str(uuid4())
                order.paypal_capture_requested_at = datetime.now(timezone.utc)
            started = order.paypal_capture_requested_at
            if started is None:
                raise OrderError("Capture attempt requires reconciliation")
            started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started
            if datetime.now(timezone.utc) - started >= timedelta(hours=6):
                raise OrderError("Uncertain capture requires reconciliation before retry")
            key, provider_id = order.paypal_capture_request_id, order.paypal_order_id
            session.commit()
            provider.capture_order(provider_id, request_id=key)
            # Ignore POST monetary data; recover the authoritative resources.
            remote = provider.get_order(provider_id)
            if remote.get('id') != provider_id:
                raise OrderError("PayPal order identity mismatch")
            validate_remote_order(order, remote, config)
            identity = remote_capture_id(remote)
            if not identity:
                raise OrderError("Capture outcome is uncertain; retry this order")
        capture = provider.get_capture(identity)
        if not isinstance(capture, dict):
            raise OrderError("PayPal capture response is invalid")
        envelope = dict(capture, _paypal_order=remote)
        reversal = session.scalar(select(PaymentEvent.id).where(PaymentEvent.provider == 'paypal',
            PaymentEvent.event_type == 'PAYMENT.CAPTURE.REVERSED',
            PaymentEvent.provider_payment_id == identity, PaymentEvent.processing_result == 'REVERSAL_QUEUED'))
        if reversal is not None:
            from .paypal_refunds import apply_paypal_reversal
            apply_paypal_reversal(session, order, client=provider)
            return 'REVERSED'
        apply_paypal_capture(session, order, envelope, config=config)
        return capture['status']
    except Exception:
        session.rollback()
        raise
    finally:
        if client is None:
            provider.close()
