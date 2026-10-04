"""Owner-approved Printful tax pass-through; no independent retail tax rates.

This records the provider estimate used to price checkout. It does not establish
tax registration, remittance or filing treatment.
"""
from datetime import datetime, timezone
import json

from .fulfillment.printful import PrintfulClient, PrintfulConfigurationError, exact_cost_cents
from .models import Order
from .settings import Settings, settings


class TaxConfigurationError(RuntimeError):
    pass


def calculate_tax_cents(order: Order, *, config: Settings = settings,
                        client: PrintfulClient | None = None) -> int:
    if config.checkout_tax_mode != "printful_quote" or not config.checkout_tax_policy_approved:
        raise TaxConfigurationError("Approved checkout tax policy is not configured")
    provider = client or PrintfulClient(config)
    try:
        estimate = provider.estimate_order_costs(order)
        costs = estimate.get("costs") if isinstance(estimate, dict) else None
        if not isinstance(costs, dict) or costs.get("currency") != order.currency:
            raise PrintfulConfigurationError("Printful tax quote currency mismatch")
        # Missing fields are failures; only an explicit provider zero is zero.
        tax = exact_cost_cents(costs.get("tax")) + exact_cost_cents(costs.get("vat"))
        serialized = json.dumps(estimate, sort_keys=True, allow_nan=False)
    finally:
        if client is None:
            provider.client.close()
    order.printful_estimate_json = serialized
    order.printful_estimated_at = datetime.now(timezone.utc)
    return tax
