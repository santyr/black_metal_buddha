# Square Integration

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

## Decision

Use Square's hosted Checkout / Payment Links API for Phase 1.

Do not route Square ecommerce payments through LNbits.
Do not embed an independent payment processor.

## Why this pattern

The Square hosted-checkout approach gives Black Metal Buddha:

- our own storefront/cart/order database
- Square-hosted payment UI
- a smaller PCI/security surface
- Square order and payment identifiers
- webhook-driven payment completion
- less client-side checkout code
- a clean path to Printful automation

LNbits' Square provider demonstrated this pattern by calling Square's payment-link API and reconciling the resulting Square order/payment, but BMB will implement the pattern directly.

## Checkout creation

Server flow:

1. Load local BMB order.
2. Require `PENDING_PAYMENT`.
3. Recalculate totals from trusted data.
4. Build Square order/line items.
5. Include a BMB order reference in Square metadata/reference fields.
6. Use a stable idempotency key.
7. Call Square CreatePaymentLink.
8. Store Square payment-link ID, Square order ID, and returned checkout URL.
9. Redirect browser to Square.

Conceptual request:

```json
{
  "idempotency_key": "stable-attempt-key",
  "order": {
    "location_id": "LOCATION",
    "reference_id": "BMB-000041",
    "line_items": []
  },
  "checkout_options": {
    "redirect_url": "https://blackmetalbuddha.com/order/BMB-000041/return"
  }
}
```

Exact fields must be verified against the current Square API version during implementation.

## Shipping-address strategy

Two valid approaches exist.

### Preferred initial approach

Have Square hosted checkout collect the shipping address if current Checkout API capabilities meet our needs.

Benefits:

- less PII handled by BMB before payment
- simpler initial checkout form

### Alternative

Collect/validate shipping in BMB first, then create the Square payment link.

Use this if Printful shipping-price calculation requires the address before the Square total can be finalized.

The final choice depends on the shipping-rate strategy.

## Payment confirmation

Browser redirects are not proof of payment.

Subscribe to relevant Square payment webhooks, including payment-state changes such as `payment.updated` where appropriate.

Webhook handler:

1. read raw body
2. verify Square signature
3. deduplicate provider event
4. identify Square order/payment
5. retrieve authoritative Square payment if needed
6. map to BMB order
7. verify expected currency
8. verify expected amount
9. require `COMPLETED`
10. atomically mark BMB payment `PAID`
11. enqueue Printful fulfillment exactly once
12. return success promptly

## Reconciliation

Run recurring reconciliation for:

- payment links with stale pending orders
- Square completed payments not reflected locally
- local paid orders missing fulfillment jobs

Webhooks are primary, not exclusive.

## Refunds

Implement an admin refund workflow before public launch.

Square refund and Printful cancellation are separate operations.

## Lightning

No Lightning functionality should be implemented in BMB or LNbits for this project at this stage.

See `10_ADR_LIGHTNING_DEFERRED.md`.
