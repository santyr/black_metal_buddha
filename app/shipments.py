from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Order, Shipment
from .orders import enqueue_job


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def upsert_printful_shipment(
    session: Session,
    order: Order,
    shipment_data: dict,
    *,
    event_type: str,
    printful_order_status: str | None = None,
) -> Shipment | None:
    shipment_id = shipment_data.get("id")
    if shipment_id is None:
        return None

    external_id = str(shipment_id)
    shipment = session.scalar(
        select(Shipment).where(Shipment.printful_shipment_id == external_id)
    )
    if shipment is None:
        shipment = Shipment(
            order_id=order.id,
            printful_shipment_id=external_id,
        )
        session.add(shipment)

    shipment.status = str(
        shipment_data.get("status")
        or shipment_data.get("shipment_status")
        or shipment_data.get("delivery_status")
        or event_type
    ).upper()
    shipment.tracking_number = shipment_data.get("tracking_number") or shipment.tracking_number
    shipment.tracking_url = shipment_data.get("tracking_url") or shipment.tracking_url
    shipment.reshipment = bool(
        shipment_data.get(
            "reshipment",
            shipment_data.get("is_reshipment", shipment.reshipment),
        )
    )
    shipment.shipped_at = _parse_time(shipment_data.get("shipped_at")) or shipment.shipped_at
    shipment.delivered_at = _parse_time(shipment_data.get("delivered_at")) or shipment.delivered_at

    if event_type == "shipment_returned":
        shipment.returned_at = datetime.now(timezone.utc)
        shipment.status = "RETURNED"
    elif event_type == "shipment_delivered":
        shipment.status = "DELIVERED"
        shipment.delivered_at = shipment.delivered_at or datetime.now(timezone.utc)
    elif event_type == "shipment_sent":
        shipment.status = "SHIPPED"
        shipment.shipped_at = shipment.shipped_at or datetime.now(timezone.utc)

    pf_status = (printful_order_status or "").upper()
    if event_type == "shipment_returned":
        order.fulfillment_state = "RETURNED"
    elif pf_status == "FULFILLED":
        order.fulfillment_state = "FULFILLED"
        order.order_state = "SHIPPED"
    elif pf_status == "PARTIAL":
        order.fulfillment_state = "PARTIAL"
        order.order_state = "PARTIALLY_SHIPPED"
    elif event_type == "shipment_sent" and order.order_state not in {"SHIPPED", "PARTIALLY_SHIPPED"}:
        order.fulfillment_state = "PARTIAL"
        order.order_state = "PARTIALLY_SHIPPED"

    if event_type == "shipment_sent":
        session.flush()
        enqueue_job(session, order, f"SEND_SHIPPING_NOTIFICATION:{shipment.id}")

    session.commit()
    return shipment
