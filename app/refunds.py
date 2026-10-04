from __future__ import annotations

from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Order, Refund
from .orders import enqueue_job
from .payments.square import SquareClient


class RefundError(ValueError):
    pass


TERMINAL_REFUND_STATES = {"COMPLETED", "FAILED", "REJECTED"}


def _lock_order(session: Session, order: Order) -> None:
    # A no-op UPDATE serializes refund mutations on PostgreSQL and SQLite.
    # SELECT FOR UPDATE alone would not lock anything on SQLite.
    session.execute(update(Order).where(Order.id == order.id)
                    .values(updated_at=Order.updated_at)
                    .execution_options(synchronize_session=False))
    session.refresh(order)


def apply_refund_status(session: Session, refund: Refund, order: Order, *, status: str) -> None:
    status = status.upper()
    if status not in TERMINAL_REFUND_STATES | {"PENDING", "APPROVED", "REQUESTED"}:
        raise RefundError("Unknown refund status")
    session.flush()
    _lock_order(session, order)
    session.refresh(refund)
    if refund.order_id != order.id:
        raise RefundError("Refund does not belong to this order")
    previous_status = refund.status
    if previous_status in TERMINAL_REFUND_STATES:
        status = previous_status
    else:
        refund.status = status
    session.flush()
    refunds = session.scalars(select(Refund).where(Refund.order_id == order.id)).all()
    # Recompute the aggregate rather than incrementing a possibly stale value.
    order.refunded_cents = sum(item.amount_cents for item in refunds if item.status == "COMPLETED")
    if order.refunded_cents >= order.total_cents:
        order.refund_state = "COMPLETED"
        order.order_state = "REFUNDED"
    elif any(item.status not in TERMINAL_REFUND_STATES for item in refunds):
        order.refund_state = "PENDING"
    elif order.refunded_cents:
        order.refund_state = "PARTIAL"
    else:
        order.refund_state = "FAILED" if status in {"FAILED", "REJECTED"} else "NONE"
    if status == "COMPLETED" and previous_status != "COMPLETED":
        enqueue_job(session, order, f"SEND_REFUND_CONFIRMATION:{refund.id}")
    session.commit()


def submit_refund_request(session: Session, refund: Refund, order: Order, *, client: SquareClient) -> Refund:
    """Retry a persisted request with exactly the same provider idempotency key."""
    if order.payment_provider == "paypal":
        from .payments.paypal_refunds import submit_paypal_refund
        return submit_paypal_refund(session, refund, order, client=client)
    if refund.payment_provider == "paypal" or order.paypal_capture_id or refund.paypal_refund_id:
        raise RefundError("Mixed provider identifiers require review")
    if refund.order_id != order.id or not refund.idempotency_key:
        raise RefundError("Invalid persisted refund request")
    if refund.square_refund_id or refund.status != "REQUESTED":
        return refund
    try:
        data = client.refund_payment(
            payment_id=order.square_payment_id,
            amount_cents=refund.amount_cents,
            currency=refund.currency,
            reason=refund.reason or "Customer refund",
            idempotency_key=refund.idempotency_key,
        )
    except httpx.HTTPStatusError as exc:
        # A timeout, throttling, or server error can hide an accepted refund.
        # Keep its reservation and key until a retry resolves the outcome.
        if 400 <= exc.response.status_code < 500 and exc.response.status_code not in {408, 429}:
            apply_refund_status(session, refund, order, status="FAILED")
        raise
    status = str(data.get("status") or "").upper()
    if not data.get("id") or status not in TERMINAL_REFUND_STATES | {"PENDING"}:
        raise RefundError("Square refund response was incomplete")
    money = data.get("amount_money")
    if money is not None and (money.get("amount") != refund.amount_cents or money.get("currency") != refund.currency):
        raise RefundError("Square refund amount or currency mismatch")
    if data.get("payment_id") not in {None, order.square_payment_id}:
        raise RefundError("Square refund payment mismatch")
    _lock_order(session, order)
    session.refresh(refund)
    if refund.square_refund_id not in {None, str(data["id"])}:
        raise RefundError("Square refund identity mismatch")
    refund.square_refund_id = str(data["id"])
    session.flush()
    apply_refund_status(session, refund, order, status=status)
    return refund


def request_refund(session: Session, order: Order, *, amount_cents: int | None,
                   reason: str, client: SquareClient) -> Refund:
    if order.payment_provider == "paypal":
        from .payments.paypal_refunds import request_paypal_refund
        return request_paypal_refund(session, order, amount_cents=amount_cents, reason=reason, client=client)
    if order.paypal_capture_id or hasattr(client, "refund_capture"):
        raise RefundError("Mixed provider identifiers require review")
    _lock_order(session, order)
    if order.payment_state != "COMPLETED" or not order.square_payment_id:
        raise RefundError("Only completed Square payments can be refunded")
    remaining = order.total_cents - order.refunded_cents
    if remaining <= 0:
        raise RefundError("Order is already fully refunded")
    amount = remaining if amount_cents is None else amount_cents
    if amount <= 0 or amount > remaining:
        raise RefundError("Refund amount exceeds the refundable balance")
    reason = reason.strip() or "Customer refund"
    if len(reason) > 192:
        raise RefundError("Refund reason is too long")

    pending = session.scalar(select(Refund).where(
        Refund.order_id == order.id, Refund.status.not_in(TERMINAL_REFUND_STATES)
    ).order_by(Refund.id))
    if pending is not None:
        if pending.status == "REQUESTED" and not pending.square_refund_id:
            if pending.amount_cents != amount or pending.reason != reason:
                raise RefundError("An unresolved refund must be retried with the same amount and reason")
            refund = pending
        else:
            raise RefundError("A refund is already pending; wait for its final status")
    else:
        refund = Refund(order_id=order.id, payment_provider="square", square_refund_id=None,
                        idempotency_key=str(uuid4()), amount_cents=amount,
                        currency=order.currency, status="REQUESTED", reason=reason)
        session.add(refund)
        order.refund_state = "PENDING"
    # Release the DB lock only after reserving the amount and durable key.
    session.commit()
    return submit_refund_request(session, refund, order, client=client)


def get_refund_by_square_id(session: Session, square_refund_id: str) -> Refund | None:
    return session.scalar(select(Refund).where(Refund.square_refund_id == square_refund_id))
