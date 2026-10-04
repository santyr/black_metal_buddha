"""Durable, server-priced PayPal attempts. Approval alone never marks paid."""
from datetime import datetime, timedelta, timezone
import json
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import Order
from ..orders import OrderError, recalculate_total, shipping_quote_is_fresh, validate_pending_catalog
from ..settings import Settings, settings
from ..tax import calculate_tax_cents
from .paypal import PayPalClient, decimal_to_cents


def lock_order(session: Session, order: Order) -> None:
    # SQLite has no SELECT FOR UPDATE. This also serializes PostgreSQL writers.
    session.execute(update(Order).where(Order.id == order.id).values(id=Order.id))
    session.refresh(order)


def checkout_snapshot(order: Order, config: Settings) -> str:
    fields = ("id", "order_number", "currency", "subtotal_cents", "discount_cents",
              "shipping_cents", "tax_cents", "total_cents", "shipping_method",
              "customer_name", "email", "phone", "ship_address1", "ship_address2",
              "ship_city", "ship_state", "ship_postal_code", "ship_country")
    item_fields = ("id", "sku_snapshot", "name_snapshot", "size_snapshot", "color_snapshot",
                   "unit_price_cents", "quantity", "line_total_cents",
                   "printful_product_id_snapshot", "printful_variant_id_snapshot")
    value = {field: getattr(order, field) for field in fields}
    value["items"] = sorted(({field: getattr(item, field) for field in item_fields}
                            for item in order.items), key=lambda item: item["id"])
    value["merchant_id"] = config.paypal_merchant_id
    value["environment"] = config.paypal_environment
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_snapshot(order: Order, config: Settings) -> None:
    if not order.paypal_snapshot or order.paypal_snapshot != checkout_snapshot(order, config):
        raise OrderError("Checkout address, items or pricing changed; this attempt requires review")


def validate_remote_order(order: Order, remote: dict, config: Settings) -> None:
    """Bind trusted GET order data to our frozen pricing and recipient."""
    try:
        units = remote["purchase_units"]
        if remote["intent"] != "CAPTURE" or not isinstance(units, list) or len(units) != 1:
            raise ValueError
        unit = units[0]
        amount = unit["amount"]
        expected_address = {"address_line_1": order.ship_address1,
            "admin_area_2": order.ship_city, "admin_area_1": order.ship_state,
            "postal_code": order.ship_postal_code, "country_code": order.ship_country}
        if order.ship_address2:
            expected_address["address_line_2"] = order.ship_address2
        address = unit["shipping"]["address"]
        if (unit["reference_id"] != order.order_number or unit["custom_id"] != order.id
                or unit["payee"]["merchant_id"] != config.paypal_merchant_id
                or amount["currency_code"] != order.currency
                or decimal_to_cents(amount["value"]) != order.total_cents
                or unit["shipping"]["name"]["full_name"] != order.customer_name
                or any(address.get(key) != value for key, value in expected_address.items())
                or (not order.ship_address2 and address.get("address_line_2"))):
            raise ValueError
    except (KeyError, TypeError, ValueError, IndexError):
        raise OrderError("PayPal order does not match the frozen checkout") from None


def approval_url(remote: dict, config: Settings) -> str:
    hosts = {"sandbox": {"www.sandbox.paypal.com"}, "production": {"www.paypal.com", "paypal.com"}}
    for link in remote.get("links", []):
        if not isinstance(link, dict) or link.get("rel") not in {"payer-action", "approve"}:
            continue
        url = link.get("href")
        try:
            parsed = urlsplit(url)
            if (isinstance(url, str) and parsed.scheme == "https"
                    and parsed.hostname in hosts[config.paypal_environment]
                    and parsed.port in {None, 443} and not parsed.username and not parsed.password
                    and parsed.path == "/checkoutnow"
                    and parse_qs(parsed.query).get("token") == [remote["id"]]):
                return url
        except (TypeError, ValueError, KeyError):
            pass
    raise OrderError("PayPal did not return a valid approval URL")


def prepare_paypal_checkout(session: Session, order: Order, *, config: Settings = settings,
                            client: PayPalClient | None = None, printful_client=None) -> str:
    provider = client or PayPalClient(config)
    try:
        lock_order(session, order)
        if order.order_state != "PENDING_PAYMENT" or order.payment_state != "PENDING":
            raise OrderError("Checkout requires a pending order")
        if order.square_order_id or order.square_payment_link_id or order.payment_provider not in {None, "paypal"}:
            raise OrderError("This order already has a different payment attempt")
        if order.paypal_create_request_id:
            validate_snapshot(order, config)
            if order.paypal_checkout_url:
                session.commit()
                return order.paypal_checkout_url
            started = order.paypal_create_requested_at
            if started is None:
                raise OrderError("Checkout attempt requires review")
            started = started.replace(tzinfo=timezone.utc) if started.tzinfo is None else started
            if datetime.now(timezone.utc) - started >= timedelta(hours=6):
                raise OrderError("Uncertain checkout attempt requires reconciliation before retry")
        else:
            if order.currency != "USD" or order.ship_country not in {"US", "CA"}:
                raise OrderError("Checkout supports USD and US/Canada delivery")
            if not config.paypal_merchant_id:
                raise OrderError("PayPal merchant is not configured")
            validate_pending_catalog(session, order)
            if not shipping_quote_is_fresh(order):
                raise OrderError("Select a fresh shipping quote before checkout")
            order.tax_cents = calculate_tax_cents(order, config=config, client=printful_client)
            recalculate_total(order)
            order.payment_provider = "paypal"
            order.paypal_snapshot = checkout_snapshot(order, config)
            order.paypal_create_request_id = str(uuid4())
            order.paypal_create_requested_at = datetime.now(timezone.utc)
        # Write the quote, snapshot and key BEFORE any financial provider call.
        key = order.paypal_create_request_id
        session.commit()
        created = provider.create_order(order, request_id=key)
        identity = created.get("id") if isinstance(created, dict) else None
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identity):
            raise OrderError("PayPal did not return a valid order ID")
        remote = provider.get_order(identity)
        if remote.get("id") != identity or remote.get("status") not in {"CREATED", "PAYER_ACTION_REQUIRED", "APPROVED"}:
            raise OrderError("PayPal order is not available for approval")
        validate_remote_order(order, remote, config)
        url = approval_url(remote, config)
        lock_order(session, order)
        validate_snapshot(order, config)
        if order.paypal_create_request_id != key or order.paypal_order_id not in {None, identity}:
            raise OrderError("Checkout attempt changed during provider creation")
        order.paypal_order_id = identity
        order.paypal_checkout_url = url
        session.commit()
        return url
    except Exception:
        session.rollback()
        raise
    finally:
        if client is None:
            provider.close()
