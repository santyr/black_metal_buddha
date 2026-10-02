from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

import httpx

from ..models import Order
from ..settings import Settings, settings


class SquareConfigurationError(RuntimeError):
    pass


class SquareClient:
    def __init__(self, config: Settings = settings, client: httpx.Client | None = None):
        self.config = config
        self.client = client or httpx.Client(timeout=20)

    def _headers(self) -> dict[str, str]:
        if not self.config.square_access_token:
            raise SquareConfigurationError("SQUARE_ACCESS_TOKEN is not configured")
        return {
            "Authorization": f"Bearer {self.config.square_access_token}",
            "Square-Version": self.config.square_api_version,
            "Content-Type": "application/json",
        }

    def create_payment_link(self, order: Order) -> dict[str, Any]:
        if not self.config.square_location_id:
            raise SquareConfigurationError("SQUARE_LOCATION_ID is not configured")
        if not order.shipping_method:
            raise SquareConfigurationError("Shipping method must be selected before checkout")

        buyer_address = {
            "address_line_1": order.ship_address1,
            "locality": order.ship_city,
            "administrative_district_level_1": order.ship_state,
            "postal_code": order.ship_postal_code,
            "country": order.ship_country,
        }
        if order.ship_address2:
            buyer_address["address_line_2"] = order.ship_address2

        pre_populated_data = {
            "buyer_email": order.email,
        }
        if order.phone:
            pre_populated_data["buyer_phone_number"] = order.phone

        checkout_options: dict[str, Any] = {
            "redirect_url": f"{self.config.public_base_url}/orders/{order.order_number}",
            "ask_for_shipping_address": False,
            "allow_tipping": False,
        }
        if order.shipping_cents:
            checkout_options["shipping_fee"] = {
                "name": order.shipping_method,
                "charge": {
                    "amount": order.shipping_cents,
                    "currency": order.currency,
                },
            }

        payload = {
            "idempotency_key": f"checkout-{order.order_number}",
            "description": f"Black Metal Buddha order {order.order_number}",
            "order": {
                "location_id": self.config.square_location_id,
                "reference_id": order.order_number,
                "pricing_options": {
                    "auto_apply_taxes": True,
                },
                "fulfillments": [
                    {
                        "type": "SHIPMENT",
                        "shipment_details": {
                            "recipient": {
                                "display_name": order.customer_name,
                                "email_address": order.email,
                                **({"phone_number": order.phone} if order.phone else {}),
                                "address": buyer_address,
                            }
                        },
                    }
                ],
                "line_items": [
                    {
                        "name": item.name_snapshot,
                        "quantity": str(item.quantity),
                        "base_price_money": {
                            "amount": item.unit_price_cents,
                            "currency": order.currency,
                        },
                        "variation_name": f"{item.color_snapshot} / {item.size_snapshot}",
                    }
                    for item in order.items
                ],
            },
            "checkout_options": checkout_options,
            "pre_populated_data": pre_populated_data,
            "payment_note": order.order_number,
        }

        response = self.client.post(
            f"{self.config.square_api_base}/v2/online-checkout/payment-links",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        payment_link = response.json().get("payment_link") or {}
        if not payment_link.get("id") or not payment_link.get("order_id") or not payment_link.get("url"):
            raise RuntimeError("Square response did not contain a complete payment link")
        return payment_link

    def get_order(self, order_id: str) -> dict[str, Any]:
        response = self.client.get(
            f"{self.config.square_api_base}/v2/orders/{order_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("order") or {}

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        response = self.client.get(
            f"{self.config.square_api_base}/v2/payments/{payment_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("payment") or {}

    def get_refund(self, refund_id: str) -> dict[str, Any]:
        response = self.client.get(
            f"{self.config.square_api_base}/v2/refunds/{refund_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json().get("refund") or {}

    def refund_payment(
        self,
        *,
        payment_id: str,
        amount_cents: int,
        currency: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = {
            "idempotency_key": idempotency_key,
            "payment_id": payment_id,
            "amount_money": {
                "amount": amount_cents,
                "currency": currency,
            },
            "reason": reason,
        }
        response = self.client.post(
            f"{self.config.square_api_base}/v2/refunds",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        refund = response.json().get("refund") or {}
        if not refund.get("id") or not refund.get("status"):
            raise RuntimeError("Square refund response was incomplete")
        return refund

    @staticmethod
    def payment_id_from_order(order: dict[str, Any]) -> str | None:
        for tender in order.get("tenders") or []:
            payment_id = tender.get("payment_id")
            if payment_id:
                return str(payment_id)
        return None


def verify_square_webhook(
    body: bytes,
    signature: str | None,
    *,
    signature_key: str | None = None,
    notification_url: str | None = None,
) -> bool:
    key = signature_key or settings.square_webhook_signature_key
    url = notification_url or settings.square_webhook_notification_url
    if not signature or not key or not url:
        return False
    digest = hmac.new(key.encode(), url.encode() + body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected.encode("ascii"), signature.encode("utf-8"))
