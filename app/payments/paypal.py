"""PayPal Orders v2/Payments v2 transport, with no local payment state changes.

Callers persist a distinct request ID for each create/capture/refund operation
before calling this client. Bounded retries reuse that ID and payload. Durable
recovery must reconcile provider state and its idempotency retention window.
"""
from __future__ import annotations

import re
import time
from threading import Lock
from typing import Any, Callable
from urllib.parse import quote

import httpx

from ..models import Order
from ..settings import Settings, settings


class PayPalConfigurationError(RuntimeError):
    pass


class PayPalAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class PayPalRetryableError(PayPalAPIError):
    """Unknown outcome/outage: retain durable operation IDs and reconcile."""


def cents_to_decimal(cents: int) -> str:
    if type(cents) is not int or cents < 0:
        raise ValueError("Money must be nonnegative integer cents")
    value = f"{cents // 100}.{cents % 100:02d}"
    if len(value) > 32:
        raise ValueError("Money exceeds PayPal's supported representation")
    return value


def decimal_to_cents(value: str) -> int:
    if not isinstance(value, str) or len(value) > 32 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value):
        raise ValueError("Money must be an exact nonnegative decimal string")
    whole, _, fraction = value.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0") or "0")


def _resource_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Invalid PayPal resource ID")
    return value


def _request_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,38}", value):
        raise ValueError("PayPal request IDs require 1–38 ASCII letters, digits, underscores or hyphens")
    return value


class PayPalClient:
    def __init__(self, config: Settings = settings, client: httpx.Client | None = None,
                 *, clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep):
        self.config = config
        self.base_url = config.paypal_api_base
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_client = client is None
        self._clock, self._sleep = clock, sleeper
        self._token: str | None = None
        self._token_expires = 0.0
        self._token_lock = Lock()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "PayPalClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _require_credentials(self) -> None:
        if not (self.config.paypal_client_id and self.config.paypal_client_secret
                and self.config.paypal_merchant_id):
            raise PayPalConfigurationError("PayPal client ID, client secret and merchant ID are required")

    def _access_token(self) -> str:
        self._require_credentials()
        with self._token_lock:
            if self._token and self._clock() < self._token_expires:
                return self._token
            started_at = self._clock()
            for attempt in range(3):
                try:
                    response = self.client.post(
                        f"{self.base_url}/v1/oauth2/token",
                        auth=httpx.BasicAuth(self.config.paypal_client_id, self.config.paypal_client_secret),
                        data={"grant_type": "client_credentials"},
                        headers={"Accept": "application/json"}, timeout=20, follow_redirects=False,
                    )
                except httpx.TransportError:
                    if attempt == 2:
                        raise PayPalRetryableError("PayPal authentication is temporarily unavailable") from None
                    self._sleep(0.25 * (attempt + 1))
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 2:
                        raise PayPalRetryableError("PayPal authentication is temporarily unavailable", status_code=response.status_code)
                    self._sleep(0.25 * (attempt + 1))
                    continue
                if not 200 <= response.status_code < 300:
                    raise PayPalAPIError("PayPal authentication was rejected", status_code=response.status_code)
                data = self._json(response)
                token, expires, kind = data.get("access_token"), data.get("expires_in"), data.get("token_type")
                if (not isinstance(token, str) or not token or not isinstance(kind, str) or kind.lower() != "bearer"
                        or type(expires) is not int or expires <= 0):
                    raise PayPalRetryableError("PayPal returned an incomplete authentication response")
                self._token = token
                self._token_expires = started_at + expires - min(30, expires / 10)
                return token
        raise PayPalRetryableError("PayPal authentication is temporarily unavailable")

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            raise PayPalRetryableError("PayPal returned an invalid response") from None
        if not isinstance(data, dict):
            raise PayPalRetryableError("PayPal returned an invalid response")
        return data

    def _request(self, method: str, path: str, *, payload: dict | None = None,
                 request_id: str | None = None) -> dict[str, Any]:
        # Signature verification is a read-only POST. Every financial POST must
        # carry its caller-persisted key, including when a nullable DB field was
        # accidentally passed as None at runtime.
        if request_id is not None or (method == "POST" and path != "/v1/notifications/verify-webhook-signature"):
            _request_id(request_id)
        refreshed = False
        for attempt in range(3):
            headers = {"Authorization": f"Bearer {self._access_token()}",
                       "Accept": "application/json", "Content-Type": "application/json",
                       "Prefer": "return=representation"}
            if request_id:
                headers["PayPal-Request-Id"] = request_id
            try:
                response = self.client.request(method, f"{self.base_url}{path}",
                    headers=headers, json=payload, timeout=20, follow_redirects=False)
            except httpx.TransportError:
                if attempt == 2:
                    raise PayPalRetryableError("PayPal request outcome is unknown; reconcile before retrying") from None
                self._sleep(0.25 * (attempt + 1))
                continue
            if response.status_code == 401 and not refreshed and attempt < 2:
                with self._token_lock:
                    self._token = None
                refreshed = True
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise PayPalRetryableError("PayPal request outcome is unknown; reconcile before retrying",
                                               status_code=response.status_code)
                self._sleep(0.25 * (attempt + 1))
                continue
            if not 200 <= response.status_code < 300:
                raise PayPalAPIError("PayPal request was rejected", status_code=response.status_code)
            return self._json(response)
        raise PayPalRetryableError("PayPal request outcome is unknown; reconcile before retrying")

    def create_order(self, order: Order, *, request_id: str) -> dict[str, Any]:
        if order.currency != "USD" or order.ship_country not in {"US", "CA"}:
            raise ValueError("PayPal checkout supports USD and US/Canada shipping only")
        if not order.shipping_method:
            raise ValueError("Select shipping before creating a PayPal order")
        amounts = [order.subtotal_cents, order.discount_cents, order.shipping_cents,
                   order.tax_cents, order.total_cents]
        for amount in amounts:
            cents_to_decimal(amount)
        if (order.total_cents <= 0 or order.discount_cents > order.subtotal_cents or
                order.total_cents != order.subtotal_cents - order.discount_cents + order.shipping_cents + order.tax_cents):
            raise ValueError("PayPal order totals are inconsistent")
        subtotal = 0
        items = []
        for item in order.items:
            if type(item.quantity) is not int or item.quantity < 1 or item.quantity > 10:
                raise ValueError("Invalid order quantity")
            unit_value = cents_to_decimal(item.unit_price_cents)
            if item.line_total_cents != item.unit_price_cents * item.quantity:
                raise ValueError("Invalid order line total")
            subtotal += item.line_total_cents
            items.append({"name": item.name_snapshot[:127], "sku": item.sku_snapshot[:127],
                          "quantity": str(item.quantity), "category": "PHYSICAL_GOODS",
                          "unit_amount": {"currency_code": "USD", "value": unit_value}})
        if not items or subtotal != order.subtotal_cents:
            raise ValueError("PayPal item totals are inconsistent")
        self._require_credentials()
        money = lambda cents: {"currency_code": "USD", "value": cents_to_decimal(cents)}
        address = {"address_line_1": order.ship_address1, "admin_area_2": order.ship_city,
                   "admin_area_1": order.ship_state, "postal_code": order.ship_postal_code,
                   "country_code": order.ship_country}
        if order.ship_address2:
            address["address_line_2"] = order.ship_address2
        return_url = f"{self.config.public_base_url}/orders/{quote(order.order_number, safe='')}"
        payload = {"intent": "CAPTURE", "purchase_units": [{
            "reference_id": order.order_number, "custom_id": order.id,
            "payee": {"merchant_id": self.config.paypal_merchant_id},
            "amount": {**money(order.total_cents), "breakdown": {
                "item_total": money(order.subtotal_cents), "shipping": money(order.shipping_cents),
                "tax_total": money(order.tax_cents), "discount": money(order.discount_cents)}},
            "items": items, "shipping": {"name": {"full_name": order.customer_name}, "address": address},
        }], "payment_source": {"paypal": {"experience_context": {
            "brand_name": "Black Metal Buddha", "shipping_preference": "SET_PROVIDED_ADDRESS",
            "user_action": "PAY_NOW", "return_url": return_url, "cancel_url": return_url,
        }}}}
        return self._request("POST", "/v2/checkout/orders", payload=payload, request_id=request_id)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/checkout/orders/{_resource_id(order_id)}")

    def capture_order(self, order_id: str, *, request_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v2/checkout/orders/{_resource_id(order_id)}/capture",
                             payload={}, request_id=request_id)

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/payments/captures/{_resource_id(capture_id)}")

    def refund_capture(self, capture_id: str, *, amount_cents: int, currency: str,
                       request_id: str) -> dict[str, Any]:
        value = cents_to_decimal(amount_cents)
        if currency != "USD" or amount_cents == 0:
            raise ValueError("Refunds require a positive USD amount")
        return self._request("POST", f"/v2/payments/captures/{_resource_id(capture_id)}/refund",
                             payload={"amount": {"currency_code": currency, "value": value}},
                             request_id=request_id)

    def get_refund(self, refund_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/payments/refunds/{_resource_id(refund_id)}")

    def verify_webhook(self, headers: dict, event: dict) -> bool:
        if not self.config.paypal_webhook_id:
            raise PayPalConfigurationError("PAYPAL_WEBHOOK_ID is required for signature verification")
        normalized = {str(key).lower(): value for key, value in headers.items()}
        fields = {"transmission_id": "paypal-transmission-id", "transmission_time": "paypal-transmission-time",
                  "cert_url": "paypal-cert-url", "auth_algo": "paypal-auth-algo", "transmission_sig": "paypal-transmission-sig"}
        if not isinstance(event, dict) or any(not normalized.get(header) for header in fields.values()):
            return False
        payload = {field: normalized[header] for field, header in fields.items()}
        payload.update(webhook_id=self.config.paypal_webhook_id, webhook_event=event)
        result = self._request("POST", "/v1/notifications/verify-webhook-signature", payload=payload)
        status = result.get("verification_status")
        if not isinstance(status, str) or status not in {"SUCCESS", "FAILURE"}:
            raise PayPalRetryableError("PayPal returned an incomplete verification response")
        return status == "SUCCESS"
