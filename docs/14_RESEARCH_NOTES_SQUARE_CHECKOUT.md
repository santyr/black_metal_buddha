# Research Notes — Square Hosted Checkout Pattern

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

## Finding

LNbits' current Square fiat provider uses Square's hosted online-checkout payment-link endpoint rather than a hidden or special Bitcoin API.

Its pattern is:

```text
create Square order/payment link
        ↓
redirect customer to square.link
        ↓
Square processes payment
        ↓
Square payment webhook
        ↓
retrieve/reconcile Square order/payment
        ↓
require COMPLETED
```

This is a useful pattern for BMB.

## What we adopt

- hosted Square checkout
- Square order IDs
- idempotent creation
- metadata/reference linking
- webhook signature verification
- webhook-driven payment completion
- API reconciliation after webhook or timeout

## What we do not adopt

LNbits' Square fiat-provider behavior credits an internal LNbits wallet with a satoshi-equivalent ledger balance after fiat payment.

That behavior is appropriate for LNbits wallet funding but unnecessary for BMB ecommerce.

BMB therefore calls Square directly.

## Lightning

LNbits does not solve the required BMB Lightning settlement problem.

The project requires:

```text
Lightning -> Square -> automatic USD -> normal Printful flow
```

So Lightning remains deferred until Square exposes the necessary official API.
