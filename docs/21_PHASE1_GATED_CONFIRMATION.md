# Phase 1 — Gated Printful Confirmation

This increment implements the chargeable Printful confirmation call **without enabling it**.

BMB uses Printful's v1 Orders API for saved products so each order inherits the
approved artwork and placement from its `sync_variant_id`. Draft creation uses
`POST /orders` with `items` and explicit `confirm=false`, `update_existing=false`.
Fulfillment begins only after:

```
POST /orders/{order_id}/confirm
```

Printful can calculate costs asynchronously and temporarily hold an unconfirmed
draft. Its v1 costs omit `calculation_status`; BMB treats costs as ready only
when currency and total are present. A hold without ready costs is retried and
is not recorded as a confirmed production order.

Printful v2 order creation accepts catalog variants with explicit artwork
placements; it does not accept the saved-product payload originally used here.
The application still uses v2 shipping quotes and signed webhook verification.

Reference:

- https://developers.printful.com/docs/#tag/Orders-API
- https://developers.printful.com/docs/v2-beta/

## Activation gates

A chargeable Printful confirmation requires all of:

```
PRINTFUL_MODE=production
PHASE0_5_APPROVED=true
PRINTFUL_CONFIRM_ENABLED=true
```

If `PRINTFUL_MODE=production` is selected without both explicit approval flags, the application refuses to start.

The public Square checkout remains separately blocked in production, so these variables alone do not launch the store.

## Confirmation sequence

For a paid BMB order the worker:

1. retrieves Printful by `@BMB-order-number`
2. creates a draft only if none exists
3. records the Printful order ID
4. reads Printful's fulfillment costs
5. waits/retries while `calculation_status != done`
6. verifies Printful cost currency equals the BMB order currency
7. verifies Printful's total charge does not exceed the customer's BMB order total
8. checks whether Printful already shows a confirmed state
9. calls the confirmation endpoint only if the order still needs confirmation
10. records `printful_confirmed_at` and the provider status

## Network/idempotency behavior

If a confirmation request succeeds at Printful but the HTTP response is lost, the next worker attempt retrieves the existing Printful order.

These statuses are considered already confirmed:

- pending
- inreview
- inprocess
- onhold
- partial
- fulfilled

The worker does not call confirmation again for those states.

## Cost guard

BMB records:

- `printful_cost_status`
- `printful_cost_currency`
- `printful_cost_cents`
- `printful_confirmed_at`

If the Printful charge currency differs from the customer order currency, confirmation is permanently blocked.

If the Printful total exceeds the customer's BMB total, confirmation is permanently blocked and the order enters `FULFILLMENT_FAILED`.

This guard is intentionally conservative. A fulfillment-cost overrun should require owner review rather than automatically losing money.

## Current status

The code path exists for testing and future canary use.

Keep:

```
PRINTFUL_MODE=disabled
PHASE0_5_APPROVED=false
PRINTFUL_CONFIRM_ENABLED=false
```

until the physical sample program has passed and an explicit production canary is authorized.

## Production canary sequence

After sample approval, but before public checkout:

1. record final Printful product/variant mappings
2. record final retail prices
3. set up the production database and migrate it
4. configure live Printful credentials
5. verify shipping quote behavior
6. configure transactional email
7. set `PHASE0_5_APPROVED=true`
8. set `PRINTFUL_MODE=production`
9. set `PRINTFUL_CONFIRM_ENABLED=true`
10. create **one controlled owner canary order**
11. verify Printful cost guard
12. verify exactly one confirmation
13. verify production status/webhooks/tracking
14. return `PRINTFUL_CONFIRM_ENABLED=false` if any unexpected behavior occurs

Public production Square checkout remains a separate final gate.
