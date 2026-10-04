# Operations Runbook

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## Automated alerts

Alert on:

- paid order with no Printful order
- Printful failure
- prolonged hold
- Printful billing failure
- PayPal reconciliation mismatch
- repeated invalid webhook signatures
- repeatedly failing jobs
- TLS renewal issue
- DB backup failure

## Owner summary

Track:

```text
New orders
Paid
Submitted
In production
Shipped
Failed/held
Refunded
Gross sales
Estimated fulfillment cost
Needs attention
```

## Investigating an order

For `BMB-000041`:

1. inspect local order
2. inspect payment events
3. retrieve PayPal payment
4. inspect job history
5. retrieve Printful by `@BMB-000041`
6. inspect fulfillment events
7. reconcile
8. audit-log manual changes

## Refund process

1. check fulfillment state
2. decide whether Printful cancellation is possible
3. process PayPal refund
4. update local payment state
5. update fulfillment separately
6. notify customer

## Reconciliation

### PayPal

Find stale pending orders and payment-state mismatches.

### Printful

Find:

- paid/no fulfillment
- submitted/missing
- failed/held
- shipped locally stale
