from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Any

import httpx

from ..models import Order
from ..settings import Settings, settings


class PrintfulConfigurationError(RuntimeError):
    pass


class PrintfulCostGuardError(RuntimeError):
    pass


def money_to_cents(value: str | int | float | Decimal) -> int:
    return int((Decimal(str(value)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def exact_cost_cents(value: Any) -> int:
    """Reject incomplete, negative and sub-cent quote values instead of rounding."""
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
        raise PrintfulConfigurationError("Printful estimate contains an invalid cost")
    try:
        representation = str(value)
        if len(representation) > 64:
            raise PrintfulConfigurationError("Printful estimate contains an invalid cost")
        amount = Decimal(representation)
        if not amount.is_finite() or amount < 0 or amount > Decimal("92233720368547758.07"):
            raise PrintfulConfigurationError("Printful estimate contains an invalid cost")
        # Use digits directly: Decimal arithmetic can round under its context.
        _, digits, exponent = amount.as_tuple()
        if not any(digits):
            return 0
        if exponent < -2:
            remove = -exponent - 2
            if remove >= len(digits) or any(digits[-remove:]):
                raise PrintfulConfigurationError("Printful estimate contains an invalid cost")
            digits = digits[:-remove]
            exponent = -2
        coefficient = int(''.join(str(digit) for digit in digits))
        return coefficient * 10 ** (exponent + 2)
    except (InvalidOperation, ValueError, OverflowError):
        raise PrintfulConfigurationError("Printful estimate contains an invalid cost") from None


def _retail_decimal(cents: int) -> str:
    if type(cents) is not int or cents < 0:
        raise PrintfulConfigurationError("Retail prices must be nonnegative integer cents")
    return f"{cents // 100}.{cents % 100:02d}"


class PrintfulClient:
    API_BASE = "https://api.printful.com"

    def __init__(self, config: Settings = settings, client: httpx.Client | None = None):
        self.config = config
        self.client = client or httpx.Client(timeout=30)

    def _headers(self) -> dict[str, str]:
        if not self.config.printful_token:
            raise PrintfulConfigurationError("PRINTFUL_TOKEN is not configured")
        headers = {
            "Authorization": f"Bearer {self.config.printful_token}",
            "Content-Type": "application/json",
        }
        if self.config.printful_store_id:
            headers["X-PF-Store-Id"] = self.config.printful_store_id
        return headers

    @staticmethod
    def _recipient(order: Order) -> dict[str, Any]:
        recipient = {
            "name": order.customer_name,
            "email": order.email,
            "address1": order.ship_address1,
            "city": order.ship_city,
            "state_name": order.ship_state,
            "state_code": order.ship_state,
            "country_code": order.ship_country,
            "zip": order.ship_postal_code,
        }
        if order.phone:
            recipient["phone"] = order.phone
        if order.ship_address2:
            recipient["address2"] = order.ship_address2
        return recipient

    @staticmethod
    def _order_items(order: Order) -> list[dict[str, Any]]:
        order_items = []
        for item in order.items:
            if not item.printful_product_id_snapshot or not item.printful_variant_id_snapshot:
                raise PrintfulConfigurationError(f"Missing Printful mapping for {item.sku_snapshot}")
            order_items.append(
                {
                    # v1 uses the saved variant with its approved artwork and
                    # placement. A catalog variant alone describes a blank.
                    "sync_variant_id": int(item.printful_variant_id_snapshot),
                    "quantity": item.quantity,
                    "external_id": f"{order.order_number}-{item.id}",
                }
            )
        return order_items

    def _shipping_items(self, order: Order) -> list[dict[str, Any]]:
        items = []
        for item in order.items:
            if not item.printful_product_id_snapshot or not item.printful_variant_id_snapshot:
                raise PrintfulConfigurationError(f"Missing Printful mapping for {item.sku_snapshot}")
            response = self.client.get(
                f"{self.API_BASE}/store/variants/{item.printful_variant_id_snapshot}",
                headers=self._headers(),
            )
            response.raise_for_status()
            variant = response.json().get("result") or {}
            if (
                str(variant.get("id")) != item.printful_variant_id_snapshot
                or str(variant.get("sync_product_id")) != item.printful_product_id_snapshot
                or variant.get("synced") is not True
                or not isinstance(variant.get("variant_id"), int)
                or variant["variant_id"] <= 0
            ):
                raise PrintfulConfigurationError(f"Invalid saved Printful variant for {item.sku_snapshot}")
            items.append({
                "source": "catalog",
                "catalog_variant_id": variant["variant_id"],
                "quantity": item.quantity,
            })
        return items

    def get_shipping_rates(self, order: Order) -> list[dict[str, Any]]:
        payload = {
            "recipient": self._recipient(order),
            "order_items": self._shipping_items(order),
            "currency": order.currency,
        }
        response = self.client.post(
            f"{self.API_BASE}/v2/shipping-rates",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        rates = []
        for rate in data:
            rates.append(
                {
                    "shipping": str(rate.get("shipping") or ""),
                    "name": str(rate.get("shipping_method_name") or rate.get("shipping") or ""),
                    "rate_cents": money_to_cents(rate.get("rate", "0")),
                    "currency": str(rate.get("currency") or order.currency),
                    "min_delivery_days": rate.get("min_delivery_days"),
                    "max_delivery_days": rate.get("max_delivery_days"),
                }
            )
        return rates

    def estimate_order_costs(self, order: Order) -> dict[str, Any]:
        """Read an estimate without creating, confirming or charging an order.

        Retail prices are supplied for destinations where Printful's calculation
        uses them. The returned costs are supplier charges; this method makes no
        decision about what BMB charges the buyer or how BMB files tax returns.
        Quotes can run with fulfillment disabled; staging still mocks the call.
        """
        if not order.shipping_method:
            raise PrintfulConfigurationError("Select shipping before estimating costs")
        if order.currency != "USD" or order.ship_country not in {"US", "CA"}:
            raise PrintfulConfigurationError("Cost estimates require USD and US/Canada shipping")
        items = self._order_items(order)
        subtotal = 0
        for payload, item in zip(items, order.items):
            if type(item.quantity) is not int or not 1 <= item.quantity <= 10:
                raise PrintfulConfigurationError("Invalid item quantity")
            payload["retail_price"] = _retail_decimal(item.unit_price_cents)
            subtotal += item.unit_price_cents * item.quantity
        if not items or subtotal != order.subtotal_cents or not 0 <= order.discount_cents <= subtotal:
            raise PrintfulConfigurationError("Retail item totals are inconsistent")
        payload = {
            "shipping": order.shipping_method, "recipient": self._recipient(order), "items": items,
            "retail_costs": {"currency": order.currency,
                "subtotal": _retail_decimal(order.subtotal_cents),
                "discount": _retail_decimal(order.discount_cents),
                "shipping": _retail_decimal(order.shipping_cents)},
        }
        response = self.client.post(f"{self.API_BASE}/orders/estimate-costs",
                                    headers=self._headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        result = data.get("result") if isinstance(data, dict) else None
        costs = result.get("costs") if isinstance(result, dict) else None
        if not isinstance(costs, dict) or costs.get("currency") != order.currency:
            raise PrintfulConfigurationError("Printful estimate is incomplete or has the wrong currency")
        if costs.get("calculation_status") not in (None, "done"):
            raise PrintfulConfigurationError("Printful estimate is still calculating")
        required = ("subtotal", "discount", "shipping", "tax", "vat", "total")
        if any(key not in costs for key in required):
            raise PrintfulConfigurationError("Printful estimate is incomplete")
        amounts = {key: exact_cost_cents(costs[key]) for key in required}
        minimum_total = amounts["subtotal"] - amounts["discount"] + amounts["shipping"] + amounts["tax"] + amounts["vat"]
        if amounts["discount"] > amounts["subtotal"] or minimum_total > amounts["total"]:
            raise PrintfulConfigurationError("Printful estimate totals are inconsistent")
        return result

    def cancel_order(self, order_id_or_external_id: str) -> dict[str, Any]:
        # Printful currently documents cancellation through the v1 DELETE
        # endpoint for pending/draft orders, including charged-order refunds.
        response = self.client.delete(
            f"https://api.printful.com/orders/{order_id_or_external_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("result") or {}

    def confirm_order(self, order_id_or_external_id: str) -> dict[str, Any]:
        if self.config.printful_mode != "production":
            raise PrintfulConfigurationError("Printful confirmation requires production mode")
        if not self.config.phase0_5_approved or not self.config.printful_confirm_enabled:
            raise PrintfulConfigurationError("Printful confirmation gates are not satisfied")

        response = self.client.post(
            f"{self.API_BASE}/orders/{order_id_or_external_id}/confirm",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("result") or {}

    def get_shipments(self, order_id_or_external_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.API_BASE}/orders/{order_id_or_external_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        shipments = (response.json().get("result") or {}).get("shipments") or []
        for shipment in shipments:
            # v1 timestamps are Unix seconds; the application consumes ISO time.
            for field in ("shipped_at", "delivered_at"):
                value = shipment.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    shipment[field] = datetime.fromtimestamp(value, timezone.utc).isoformat()
        return shipments

    def get_order_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        response = self.client.get(
            f"{self.API_BASE}/orders/@{external_id}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("result") or {}

    def create_draft_order(self, order: Order) -> dict[str, Any]:
        if self.config.printful_mode == "disabled":
            raise PrintfulConfigurationError("Printful integration is disabled")
        if not order.shipping_method:
            raise PrintfulConfigurationError("Shipping method has not been selected")

        payload = {
            "external_id": order.order_number,
            "shipping": order.shipping_method,
            "recipient": self._recipient(order),
            "items": self._order_items(order),
        }

        response = self.client.post(
            f"{self.API_BASE}/orders",
            headers=self._headers(),
            json=payload,
            params={"confirm": "false", "update_existing": "false"},
        )
        response.raise_for_status()
        return response.json().get("result") or {}


def verify_printful_webhook(
    body: bytes,
    signature: str | None,
    *,
    secret_key_hex: str | None = None,
) -> bool:
    secret_hex = secret_key_hex or settings.printful_webhook_secret_key
    if not signature or not secret_hex:
        return False
    try:
        secret = bytes.fromhex(secret_hex)
    except ValueError:
        return False
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode("ascii"), signature.encode("utf-8"))


def extract_printful_costs(data: dict[str, Any]) -> tuple[str, str | None, int | None]:
    costs = data.get("costs") or {}
    status = str(costs.get("calculation_status") or "").lower()
    currency = costs.get("currency")
    total = costs.get("total")
    cents = money_to_cents(total) if total is not None else None
    if not status:
        # Saved-product orders use v1, which omits calculation_status.
        status = "done" if currency and cents is not None else "calculating"
    return status, str(currency) if currency else None, cents
