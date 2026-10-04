from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PrintfulProduct(Base):
    __tablename__ = "printful_products"

    printful_product_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    garment_name: Mapped[str] = mapped_column(String(255))
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_last_modified: Mapped[str | None] = mapped_column(String(128), nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PrintfulCatalogState(Base):
    __tablename__ = "printful_catalog_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[str] = mapped_column(String(128))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    product_count: Mapped[int] = mapped_column(Integer)
    variant_count: Mapped[int] = mapped_column(Integer)


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_slug: Mapped[str] = mapped_column(String(128), index=True)
    sku: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    size: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(64), default="Black")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    retail_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    sellable: Mapped[bool] = mapped_column(Boolean, default=False)
    catalog_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    printful_product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    printful_variant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    customer_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ship_address1: Mapped[str] = mapped_column(String(255))
    ship_address2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_city: Mapped[str] = mapped_column(String(128))
    ship_state: Mapped[str] = mapped_column(String(128))
    ship_postal_code: Mapped[str] = mapped_column(String(32))
    ship_country: Mapped[str] = mapped_column(String(2), default="US")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer)
    refunded_cents: Mapped[int] = mapped_column(Integer, default=0)
    refund_state: Mapped[str] = mapped_column(String(32), default="NONE")
    payment_state: Mapped[str] = mapped_column(String(32), default="PENDING")
    fulfillment_state: Mapped[str] = mapped_column(String(32), default="NOT_STARTED")
    order_state: Mapped[str] = mapped_column(String(32), default="PENDING_PAYMENT")
    is_canary: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    paypal_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    paypal_checkout_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    paypal_create_request_id: Mapped[str | None] = mapped_column(String(38), unique=True, nullable=True)
    paypal_capture_request_id: Mapped[str | None] = mapped_column(String(38), unique=True, nullable=True)
    paypal_create_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paypal_capture_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    square_payment_link_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    square_checkout_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    square_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    square_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    printful_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    printful_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    printful_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printful_cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    printful_cost_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    printful_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_to_printful_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    sku_snapshot: Mapped[str] = mapped_column(String(128))
    name_snapshot: Mapped[str] = mapped_column(String(255))
    size_snapshot: Mapped[str] = mapped_column(String(32))
    color_snapshot: Mapped[str] = mapped_column(String(64))
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total_cents: Mapped[int] = mapped_column(Integer)
    printful_product_id_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    printful_variant_id_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order: Mapped[Order] = relationship(back_populates="items")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    printful_shipment_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    tracking_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    reshipment: Mapped[bool] = mapped_column(Boolean, default=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    order: Mapped[Order] = relationship(back_populates="shipments")


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    payment_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    paypal_refund_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    paypal_request_id: Mapped[str | None] = mapped_column(String(38), unique=True, nullable=True)
    paypal_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    square_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(45), unique=True, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(192), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_event_id: Mapped[str] = mapped_column(String(128))
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(128))
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    processing_result: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FulfillmentEvent(Base):
    __tablename__ = "fulfillment_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_event_id: Mapped[str] = mapped_column(String(128))
    provider_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    processing_result: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), index=True)
    object_type: Mapped[str] = mapped_column(String(64), index=True)
    object_id: Mapped[str] = mapped_column(String(128), index=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("job_type", "order_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
