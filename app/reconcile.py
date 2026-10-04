from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .fulfillment.printful import PrintfulClient
from .models import Order, Refund
from .orders import mark_paid_and_enqueue, sync_square_pricing
from .payments.square import SquareClient
from .payments.paypal import PayPalClient
from .payments.paypal_capture import capture_paypal_order
from .payments.paypal_checkout import prepare_paypal_checkout
from .refunds import TERMINAL_REFUND_STATES, apply_refund_status, submit_refund_request
from .shipments import upsert_printful_shipment


class ReconciliationError(RuntimeError):
    pass


def _validate_square_amount(order: Order, payment: dict) -> None:
    amount = payment.get("amount_money") or {}
    if amount.get("currency") != order.currency:
        raise ReconciliationError(
            f"Square currency mismatch for {order.order_number}: "
            f"{amount.get('currency')} != {order.currency}"
        )
    if int(amount.get("amount", -1)) != order.total_cents:
        raise ReconciliationError(
            f"Square amount mismatch for {order.order_number}: "
            f"{amount.get('amount')} != {order.total_cents}"
        )


def reconcile_square_order(
    session: Session,
    order: Order,
    *,
    client: SquareClient,
) -> str:
    if not order.square_order_id:
        return "NO_SQUARE_ORDER"

    square_order = client.get_order(order.square_order_id)
    sync_square_pricing(session, order, square_order)
    payment_id = client.payment_id_from_order(square_order)
    if not payment_id:
        return "NO_PAYMENT"

    payment = client.get_payment(payment_id)
    _validate_square_amount(order, payment)
    status = (payment.get("status") or "").upper()

    if status == "COMPLETED":
        mark_paid_and_enqueue(session, order, square_payment_id=payment_id)
        return "PAID"

    if status in {"FAILED", "CANCELED"} and order.payment_state != "COMPLETED":
        order.payment_state = status
        order.order_state = "PAYMENT_FAILED"
        session.commit()
        return status

    if payment_id and not order.square_payment_id:
        order.square_payment_id = payment_id
        session.commit()

    return status or "PENDING"


def reconcile_printful_order(
    session: Session,
    order: Order,
    *,
    client: PrintfulClient,
) -> str:
    data = client.get_order_by_external_id(order.order_number)
    if data is None:
        return "MISSING"

    if data.get("id") is not None:
        order.printful_order_id = str(data["id"])

    status = (data.get("status") or "").upper()
    if status == "FAILED":
        order.fulfillment_state = "FAILED"
        order.order_state = "FULFILLMENT_FAILED"
    elif status == "CANCELED":
        order.fulfillment_state = "CANCELED"
    elif status == "ONHOLD":
        order.fulfillment_state = "HOLD"
        order.order_state = "FULFILLMENT_HOLD"
    elif status in {"PENDING", "INREVIEW", "INPROCESS"}:
        order.fulfillment_state = status
        order.order_state = "IN_PRODUCTION"
    elif status == "PARTIAL":
        order.fulfillment_state = "PARTIAL"
        order.order_state = "PARTIALLY_SHIPPED"
    elif status == "FULFILLED":
        order.fulfillment_state = "FULFILLED"
        order.order_state = "SHIPPED"
    elif status == "DRAFT":
        order.fulfillment_state = "DRAFT"
        if order.order_state == "PAID":
            order.order_state = "FULFILLMENT_SUBMITTED"
    else:
        order.fulfillment_state = status or order.fulfillment_state

    session.commit()

    for shipment_data in client.get_shipments(f"@{order.order_number}"):
        delivery_status = str(shipment_data.get("delivery_status") or "").lower()
        shipment_status = str(shipment_data.get("shipment_status") or "").lower()
        if shipment_data.get("delivered_at") or delivery_status == "delivered":
            event_type = "shipment_delivered"
        elif shipment_status == "returned":
            event_type = "shipment_returned"
        elif shipment_data.get("shipped_at"):
            event_type = "shipment_sent"
        else:
            event_type = "shipment_reconciled"
        upsert_printful_shipment(
            session,
            order,
            shipment_data,
            event_type=event_type,
            printful_order_status=status,
        )

    return status or "UNKNOWN"


def reconcile_orders(
    session: Session,
    *,
    square_client: SquareClient | None = None,
    paypal_client: PayPalClient | None = None,
    printful_client: PrintfulClient | None = None,
    limit: int = 100,
) -> dict[str, int]:
    counts = {
        "square_checked": 0,
        "square_errors": 0,
        "paypal_checked": 0,
        "paypal_errors": 0,
        "refunds_checked": 0,
        "refund_errors": 0,
        "printful_checked": 0,
        "printful_errors": 0,
    }

    if square_client is None and paypal_client is None and printful_client is None:
        return counts
    # Rotate through the oldest checked records. Selecting the newest orders
    # every run permanently starves everything outside the first batch.
    orders = session.scalars(
        select(Order).order_by(Order.updated_at, Order.id).limit(limit)
    ).all()

    for order in orders:
        if paypal_client is not None and order.payment_provider == "paypal":
            try:
                if not order.paypal_order_id and order.paypal_create_request_id:
                    prepare_paypal_checkout(session, order, client=paypal_client, config=paypal_client.config)
                capture_paypal_order(session, order, client=paypal_client, config=paypal_client.config)
                counts["paypal_checked"] += 1
            except Exception:
                session.rollback()
                counts["paypal_errors"] += 1
        if square_client is not None and order.square_order_id:
            try:
                reconcile_square_order(session, order, client=square_client)
                counts["square_checked"] += 1
            except Exception:
                session.rollback()
                counts["square_errors"] += 1

        if square_client is not None and order.payment_provider != "paypal":
            refunds = session.scalars(
                select(Refund).where(
                    Refund.order_id == order.id,
                    Refund.status.not_in(TERMINAL_REFUND_STATES),
                )
            ).all()
            for refund in refunds:
                try:
                    if refund.status == "REQUESTED" and not refund.square_refund_id:
                        submit_refund_request(session, refund, order, client=square_client)
                        counts["refunds_checked"] += 1
                        continue
                    data = square_client.get_refund(refund.square_refund_id)
                    apply_refund_status(
                        session,
                        refund,
                        order,
                        status=str(data.get("status") or refund.status),
                    )
                    counts["refunds_checked"] += 1
                except Exception:
                    session.rollback()
                    counts["refund_errors"] += 1

        if (
            printful_client is not None
            and order.payment_state == "COMPLETED"
            and order.printful_external_id
        ):
            try:
                reconcile_printful_order(session, order, client=printful_client)
                counts["printful_checked"] += 1
            except Exception:
                session.rollback()
                counts["printful_errors"] += 1

        order.updated_at = datetime.now(timezone.utc)
        session.commit()

    return counts
