"""PayPal refund reservations and authoritative recovery, separate from Printful."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from ..models import Order, Refund, Job, PaymentEvent
from ..refunds import RefundError, TERMINAL_REFUND_STATES, _lock_order, apply_refund_status
from .paypal import decimal_to_cents
from .paypal_checkout import validate_snapshot, validate_remote_order
from .paypal_capture import remote_capture_id


def _binding(order, client, *, allow_unrecorded=False):
    if (order.payment_provider != 'paypal' or (not order.paypal_capture_id and not allow_unrecorded) or order.square_payment_id
            or order.square_order_id or not hasattr(client, 'refund_capture')):
        raise RefundError('PayPal refund requires an unmixed captured PayPal payment')
    validate_snapshot(order, client.config)
    remote = client.get_order(order.paypal_order_id)
    identity = remote_capture_id(remote)
    if not identity or order.paypal_capture_id not in {None, identity}:
        raise RefundError('PayPal refund capture binding mismatch')
    capture = client.get_capture(identity)
    validate_remote_order(order, remote, client.config)
    try:
        if (remote['id'] != order.paypal_order_id or capture['id'] != identity
                or capture['supplementary_data']['related_ids']['order_id'] != order.paypal_order_id
                or capture['payee']['merchant_id'] != client.config.paypal_merchant_id
                or capture['amount']['currency_code'] != order.currency
                or decimal_to_cents(capture['amount']['value']) != order.total_cents):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise RefundError('PayPal refund capture binding mismatch') from None
    return remote, capture


def reconcile_paypal_refund(session, order, refund_id, *, client):
    _binding(order, client)
    data = client.get_refund(refund_id)
    try:
        expected_up = client.config.paypal_api_base + '/v2/payments/captures/' + order.paypal_capture_id
        if (data['id'] != refund_id or data['amount']['currency_code'] != order.currency
                or not any(link.get('rel') == 'up' and link.get('href') == expected_up
                           for link in data['links'] if isinstance(link, dict))):
            raise ValueError
        amount = decimal_to_cents(data['amount']['value'])
        status = data['status']
        if status == 'CANCELLED':
            status = 'FAILED'
        if amount <= 0 or status not in {'COMPLETED', 'PENDING', 'FAILED'}:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise RefundError('PayPal refund identity, amount or status mismatch') from None
    _lock_order(session, order)
    validate_snapshot(order, client.config)
    refund = session.scalar(select(Refund).where(Refund.paypal_refund_id == refund_id))
    if refund is None and isinstance(data.get('custom_id'), str):
        refund = session.scalar(select(Refund).where(Refund.paypal_request_id == data['custom_id']))
    if refund is not None:
        session.refresh(refund)
        if (refund.order_id != order.id or refund.payment_provider != 'paypal' or refund.square_refund_id
                or refund.amount_cents != amount or refund.currency != order.currency
                or refund.paypal_refund_id not in {None, refund_id}):
            raise RefundError('PayPal refund does not match its local reservation')
    else:
        unresolved = session.scalar(select(Refund.id).where(Refund.order_id == order.id,
            Refund.status == 'REQUESTED', Refund.paypal_refund_id.is_(None)))
        if unresolved is not None:
            raise RefundError('Unresolved refund requires exact request identity before dashboard import')
        refund = Refund(order_id=order.id, payment_provider='paypal', amount_cents=amount,
                        currency=order.currency, status='PENDING', reason='PayPal dashboard refund')
        session.add(refund)
    other_completed = sum(item.amount_cents for item in session.scalars(select(Refund).where(
        Refund.order_id == order.id, Refund.status == 'COMPLETED')).all() if item.id != refund.id)
    if amount + other_completed > order.total_cents:
        raise RefundError('PayPal refund exceeds captured gross amount')
    refund.paypal_refund_id = refund_id
    session.flush()
    apply_refund_status(session, refund, order, status=status)
    return refund


def submit_paypal_refund(session, refund, order, *, client):
    if (refund.order_id != order.id or refund.payment_provider != 'paypal'
            or not refund.paypal_request_id or refund.square_refund_id):
        raise RefundError('Invalid PayPal refund reservation')
    if refund.paypal_refund_id:
        return reconcile_paypal_refund(session, order, refund.paypal_refund_id, client=client)
    if refund.status != 'REQUESTED':
        return refund
    remote, capture = _binding(order, client)
    # A lost POST response may already appear in GET order. Match only our key.
    for data in remote['purchase_units'][0].get('payments', {}).get('refunds', []):
        if data.get('custom_id') == refund.paypal_request_id and data.get('id'):
            return reconcile_paypal_refund(session, order, data['id'], client=client)
    started = refund.paypal_requested_at
    if started is None:
        raise RefundError('Refund request requires reconciliation')
    started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started
    if datetime.now(timezone.utc) - started >= timedelta(hours=6):
        raise RefundError('Uncertain refund requires reconciliation before retry')
    if capture.get('status') not in {'COMPLETED', 'PARTIALLY_REFUNDED'}:
        raise RefundError('PayPal capture cannot currently be refunded')
    session.commit()
    data = client.refund_capture(order.paypal_capture_id, amount_cents=refund.amount_cents,
                                currency=refund.currency, request_id=refund.paypal_request_id)
    if not isinstance(data, dict) or not isinstance(data.get('id'), str):
        raise RefundError('PayPal refund response is incomplete')
    return reconcile_paypal_refund(session, order, data['id'], client=client)


def request_paypal_refund(session, order, *, amount_cents, reason, client):
    if not hasattr(client, 'refund_capture'):
        raise RefundError('Wrong provider client for PayPal payment')
    _binding(order, client)
    _lock_order(session, order)
    if order.payment_state != 'COMPLETED':
        raise RefundError('Only completed payments can be refunded')
    remaining = order.total_cents - order.refunded_cents
    amount = remaining if amount_cents is None else amount_cents
    if type(amount) is not int or not 0 < amount <= remaining:
        raise RefundError('Refund amount exceeds the refundable balance')
    reason = reason.strip() or 'Customer refund'
    if len(reason) > 192:
        raise RefundError('Refund reason is too long')
    pending = session.scalar(select(Refund).where(Refund.order_id == order.id,
        Refund.status.not_in(TERMINAL_REFUND_STATES)).order_by(Refund.id))
    if pending is not None:
        session.refresh(pending)
        if (pending.status != 'REQUESTED' or pending.paypal_refund_id or pending.payment_provider != 'paypal'
                or pending.amount_cents != amount or pending.reason != reason):
            raise RefundError('An unresolved refund must be retried with the same amount and reason')
        refund = pending
    else:
        key = str(uuid4())
        refund = Refund(order_id=order.id, payment_provider='paypal', idempotency_key=key,
            paypal_request_id=key, paypal_requested_at=datetime.now(timezone.utc),
            amount_cents=amount, currency=order.currency, status='REQUESTED', reason=reason)
        session.add(refund)
        order.refund_state = 'PENDING'
    session.commit()
    return submit_paypal_refund(session, refund, order, client=client)


def apply_paypal_reversal(session, order, *, client):
    """Only call for a verified stored reversal event; validate provider identity."""
    _, capture = _binding(order, client, allow_unrecorded=True)
    verified = session.scalar(select(PaymentEvent.id).where(PaymentEvent.provider == 'paypal',
        PaymentEvent.event_type == 'PAYMENT.CAPTURE.REVERSED',
        PaymentEvent.provider_payment_id == capture['id'],
        PaymentEvent.processing_result == 'REVERSAL_QUEUED'))
    if verified is None:
        raise RefundError('A verified stored reversal event is required')
    _lock_order(session, order)
    order.paypal_capture_id = capture['id']
    order.payment_state = 'REVERSED'
    order.order_state = 'PAYMENT_REVERSED'
    # Printful cancellation is a separate owner action. Stop unsent jobs only.
    for job in session.scalars(select(Job).where(Job.order_id == order.id,
        Job.job_type == 'SUBMIT_PRINTFUL_ORDER', Job.state == 'PENDING')).all():
        job.state = 'CANCELED'
        job.last_error = 'PayPal reversed the capture; owner review required'
    session.commit()
