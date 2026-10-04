from __future__ import annotations

from datetime import datetime, timedelta, timezone
import httpx

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from .fulfillment.printful import (
    PrintfulClient,
    PrintfulCostGuardError,
    extract_printful_costs,
)
from .models import Job, Order, Shipment
from .notifications.email import EmailSender
from .settings import Settings, settings


def _fail_permanently(session: Session, job: Job, order: Order, exc: Exception) -> None:
    job.attempt_count += 1
    job.state = "FAILED"
    job.last_error = str(exc)[:2000]
    order.fulfillment_state = "FAILED"
    order.order_state = "FULFILLMENT_FAILED"
    session.commit()


def _retry_or_fail(session: Session, job: Job, exc: Exception) -> None:
    # Recover the transaction before writing retry state after a DB failure.
    session.rollback()
    job.attempt_count += 1
    job.state = "PENDING" if job.attempt_count < 8 else "FAILED"
    delay = min(60, 2 ** min(job.attempt_count, 6))
    job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=delay)
    job.last_error = str(exc)[:2000]
    session.commit()


def process_submit_printful_job(
    session: Session,
    job: Job,
    *,
    config: Settings = settings,
    client: PrintfulClient | None = None,
) -> None:
    order = session.get(Order, job.order_id)
    if order is None:
        job.state = "FAILED"
        job.last_error = "Order not found"
        session.commit()
        return

    # Serialize fulfillment with payment callbacks and refresh cached worker state.
    # Keep this order lock through supplier confirmation: a committed reversal wins
    # before any submission; an already-running confirmation requires owner action.
    from .payments.paypal_checkout import lock_order
    lock_order(session, order)
    if order.payment_state == "REVERSED":
        job.state = "CANCELED"
        job.last_error = "PayPal reversed the capture; owner review required"
        session.commit()
        return

    if order.order_state == "PAYMENT_REVIEW":
        job.state = "PENDING"
        job.last_error = "Recovered refunded capture; owner review required before fulfillment"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=1)
        session.commit()
        return

    if order.payment_state != "COMPLETED":
        job.state = "FAILED"
        job.last_error = "Order is not paid"
        session.commit()
        return

    if order.refund_state == "COMPLETED" or order.refunded_cents >= order.total_cents:
        job.state = "CANCELED"
        job.last_error = "Order fully refunded; fulfillment submission canceled"
        session.commit()
        return

    if order.refund_state == "PENDING":
        job.state = "PENDING"
        job.last_error = "Waiting for the pending refund to resolve before fulfillment"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        session.commit()
        return

    if config.printful_mode == "disabled":
        job.state = "PENDING"
        job.last_error = "Printful disabled by configuration"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=1)
        session.commit()
        return

    pf = client or PrintfulClient(config)
    try:
        existing = pf.get_order_by_external_id(order.order_number)
        data = existing or pf.create_draft_order(order)
        order.printful_order_id = str(data.get("id") or "")
        order.submitted_to_printful_at = order.submitted_to_printful_at or datetime.now(timezone.utc)

        cost_status, cost_currency, cost_cents = extract_printful_costs(data)
        order.printful_cost_status = cost_status or None
        order.printful_cost_currency = cost_currency
        order.printful_cost_cents = cost_cents

        provider_status = str(data.get("status") or "draft").lower()

        if config.printful_mode == "draft":
            order.fulfillment_state = provider_status.upper()
            order.order_state = "FULFILLMENT_SUBMITTED"
            job.state = "COMPLETED"
            job.last_error = None
            session.commit()
            return

        already_confirmed = provider_status in {
            "pending",
            "inreview",
            "inprocess",
            "onhold",
            "partial",
            "fulfilled",
        }
        # v1 can put an unconfirmed draft on hold while computing its costs.
        # That hold is not proof that production has been confirmed.
        if provider_status == "onhold" and cost_status != "done":
            raise RuntimeError("Printful costs are not finished calculating")
        if not already_confirmed:
            if cost_status != "done":
                raise RuntimeError("Printful costs are not finished calculating")
            if cost_currency != order.currency:
                raise PrintfulCostGuardError(
                    f"Printful cost currency {cost_currency!r} does not match {order.currency}"
                )
            if cost_cents is None:
                raise RuntimeError("Printful total cost is not available")
            if cost_cents > order.total_cents:
                raise PrintfulCostGuardError(
                    f"Printful cost {cost_cents} exceeds customer order total {order.total_cents}"
                )

            data = pf.confirm_order(f"@{order.order_number}")
            provider_status = str(data.get("status") or "pending").lower()
            cost_status, cost_currency, cost_cents = extract_printful_costs(data)
            if cost_status:
                order.printful_cost_status = cost_status
            if cost_currency:
                order.printful_cost_currency = cost_currency
            if cost_cents is not None:
                order.printful_cost_cents = cost_cents
            order.printful_confirmed_at = datetime.now(timezone.utc)
        else:
            order.printful_confirmed_at = order.printful_confirmed_at or datetime.now(timezone.utc)

        order.fulfillment_state = provider_status.upper()
        if provider_status == "partial":
            order.order_state = "PARTIALLY_SHIPPED"
        elif provider_status == "fulfilled":
            order.order_state = "SHIPPED"
        elif provider_status == "onhold":
            order.order_state = "FULFILLMENT_HOLD"
        else:
            order.order_state = "IN_PRODUCTION"

        job.state = "COMPLETED"
        job.last_error = None
        session.commit()
    except PrintfulCostGuardError as exc:
        _fail_permanently(session, job, order, exc)
    except httpx.HTTPStatusError as exc:
        _retry_or_fail(session, job, RuntimeError("Printful request failed; reconciliation required"))
        if exc.response.status_code == 402:
            order.fulfillment_state = "HOLD"
            order.order_state = "FULFILLMENT_HOLD"
            job.last_error = "Printful funding declined; owner review required"
            session.commit()
    except Exception as exc:
        _retry_or_fail(session, job, exc)


def process_email_job(
    session: Session,
    job: Job,
    *,
    config: Settings = settings,
    sender: EmailSender | None = None,
) -> None:
    order = session.get(Order, job.order_id)
    if order is None:
        job.state = "FAILED"
        job.last_error = "Order not found"
        session.commit()
        return

    if config.email_mode == "disabled":
        job.state = "PENDING"
        job.last_error = "Transactional email disabled by configuration"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=1)
        session.commit()
        return

    mailer = sender or EmailSender(config)
    try:
        if job.job_type == "SEND_ORDER_CONFIRMATION":
            mailer.send_order_confirmation(order)
        elif job.job_type.startswith("SEND_SHIPPING_NOTIFICATION:"):
            shipment_id = int(job.job_type.split(":", 1)[1])
            shipment = session.get(Shipment, shipment_id)
            if shipment is None or shipment.order_id != order.id:
                raise RuntimeError("Shipment email job references an invalid shipment")
            mailer.send_shipping_notification(order, shipment)
        elif job.job_type.startswith("SEND_REFUND_CONFIRMATION"):
            mailer.send_refund_confirmation(order)
        else:
            raise RuntimeError(f"Unknown email job type: {job.job_type}")

        job.state = "COMPLETED"
        job.last_error = None
        session.commit()
    except Exception as exc:
        _retry_or_fail(session, job, exc)


def process_paypal_capture_job(session: Session, job: Job, *, config: Settings = settings,
                               client=None) -> None:
    from .payments.paypal_capture import capture_paypal_order
    order = session.get(Order, job.order_id)
    if order is None:
        job.state = "FAILED"
        job.last_error = "Order not found"
        session.commit()
        return
    try:
        status = capture_paypal_order(session, order, config=config, client=client)
        if status in {"COMPLETED", "DECLINED", "FAILED", "VOIDED", "REFUNDED", "PARTIALLY_REFUNDED", "REVERSED"}:
            job.state = "COMPLETED"
            job.last_error = None
        else:
            job.state = "PENDING"
            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            job.last_error = "Waiting for authoritative PayPal capture completion"
        session.commit()
    except Exception as exc:
        _retry_or_fail(session, job, exc)


def process_paypal_refund_job(session: Session, job: Job, *, config: Settings = settings,
                              client=None) -> None:
    from .payments.paypal import PayPalClient
    from .payments.paypal_refunds import reconcile_paypal_refund
    from .models import Refund
    provider = client or PayPalClient(config)
    try:
        refund = session.get(Refund, int(job.job_type.split(':', 1)[1]))
        order = session.get(Order, job.order_id)
        if refund is None or order is None or refund.order_id != order.id:
            raise ValueError('Refund job identity mismatch')
        result = reconcile_paypal_refund(session, order, refund.paypal_refund_id, client=provider)
        job.state = 'PENDING' if result.status == 'PENDING' else 'COMPLETED'
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        job.last_error = None
        session.commit()
    except Exception as exc:
        _retry_or_fail(session, job, exc)
    finally:
        if client is None:
            provider.close()


def process_pending_jobs(
    session: Session,
    *,
    limit: int = 20,
    config: Settings = settings,
) -> int:
    now = datetime.now(timezone.utc)
    eligible = or_(
        and_(Job.state == "PENDING", Job.next_attempt_at <= now),
        and_(Job.state == "RUNNING", or_(Job.locked_at.is_(None),
                                        Job.locked_at <= now - timedelta(minutes=15))),
    )
    job_ids = session.scalars(
        select(Job.id)
        .where(eligible)
        .order_by(Job.created_at)
        .limit(limit)
    ).all()

    processed = 0
    for job_id in job_ids:
        claimed = session.execute(
            update(Job).where(Job.id == job_id, eligible)
            .values(state="RUNNING", locked_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        ).rowcount
        session.commit()
        if not claimed:
            continue
        session.expire_all()
        job = session.get(Job, job_id)
        try:
            if job.job_type == "SUBMIT_PRINTFUL_ORDER":
                process_submit_printful_job(session, job, config=config)
            elif job.job_type == "CAPTURE_PAYPAL_ORDER":
                process_paypal_capture_job(session, job, config=config)
            elif job.job_type.startswith("RECONCILE_PAYPAL_REFUND:"):
                process_paypal_refund_job(session, job, config=config)
            elif job.job_type.startswith("SEND_"):
                process_email_job(session, job, config=config)
            else:
                job.state = "FAILED"
                job.last_error = f"Unknown job type: {job.job_type}"
        except Exception as exc:
            _retry_or_fail(session, job, exc)
        job.locked_at = None
        session.commit()
        processed += 1
    return processed
