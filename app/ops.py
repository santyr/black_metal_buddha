from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job, Order, Refund, Shipment
from .settings import Settings, settings


def build_attention_report(
    session: Session,
    *,
    config: Settings = settings,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    paid_stale_cutoff = now - timedelta(minutes=30)

    failed_jobs = session.scalars(
        select(Job).where(Job.state == "FAILED").order_by(Job.updated_at.desc())
    ).all()
    problem_orders = session.scalars(
        select(Order).where(
            Order.order_state.in_(["FULFILLMENT_FAILED", "FULFILLMENT_HOLD", "PAYMENT_REVERSED"])
        )
    ).all()
    failed_refunds = session.scalars(
        select(Refund).where(Refund.status.in_(["FAILED", "REJECTED"]))
    ).all()
    returned_shipments = session.scalars(
        select(Shipment).where(Shipment.status == "RETURNED")
    ).all()

    stale_paid = []
    if config.printful_mode != "disabled":
        stale_paid = session.scalars(
            select(Order).where(
                Order.payment_state == "COMPLETED",
                Order.refund_state != "COMPLETED",
                Order.printful_order_id.is_(None),
                Order.paid_at.is_not(None),
                Order.paid_at <= paid_stale_cutoff,
            )
        ).all()

    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, order_number: str, detail: str) -> None:
        key = (kind, order_number)
        if key in seen:
            return
        seen.add(key)
        issues.append({"kind": kind, "order_number": order_number, "detail": detail})

    order_numbers = {
        order.id: order.order_number
        for order in session.scalars(select(Order)).all()
    }

    for job in failed_jobs:
        add(
            "failed_job",
            order_numbers.get(job.order_id, job.order_id),
            f"{job.job_type}: {job.last_error or 'no error recorded'}",
        )
    for order in problem_orders:
        add("fulfillment_problem", order.order_number, order.order_state)
    for order in stale_paid:
        add(
            "stale_paid_without_printful",
            order.order_number,
            "Paid for more than 30 minutes with no Printful order",
        )
    for refund in failed_refunds:
        add(
            "failed_refund",
            order_numbers.get(refund.order_id, refund.order_id),
            refund.paypal_refund_id or refund.square_refund_id or f"Request {refund.paypal_request_id or refund.idempotency_key}",
        )
    for shipment in returned_shipments:
        add(
            "returned_shipment",
            order_numbers.get(shipment.order_id, shipment.order_id),
            shipment.printful_shipment_id,
        )

    counts = {
        "failed_jobs": len(failed_jobs),
        "problem_orders": len(problem_orders),
        "stale_paid_without_printful": len(stale_paid),
        "failed_refunds": len(failed_refunds),
        "returned_shipments": len(returned_shipments),
        "attention_total": len(issues),
    }
    return {
        "generated_at": now.isoformat(),
        "counts": counts,
        "issues": issues,
    }
