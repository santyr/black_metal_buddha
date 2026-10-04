# Phase 1 — Owner Admin & Production Controls

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

## Owner console

The owner console lives at:

```
/admin
```

It is hidden unless all three values are configured:

```
APP_SECRET_KEY
ADMIN_USERNAME
ADMIN_PASSWORD
```

Authentication uses HTTP Basic and must only be exposed behind HTTPS.

The console is `noindex,nofollow` and provides:

- operations dashboard
- attention items
- recent orders
- order search/filter
- complete order detail
- shipping/tracking records
- background jobs/errors
- provider IDs
- refunds
- per-order audit history
- manual provider reconciliation
- retry of failed jobs
- catalog/variant creation and editing
- global admin audit log

## CSRF

All mutating admin forms carry an HMAC token bound to:

```
action | object-id
```

The token is generated with `APP_SECRET_KEY` and verified using constant-time comparison.

## Destructive action kill switches

Financial/destructive operations are separately disabled by default:

```
ADMIN_REFUNDS_ENABLED=false
ADMIN_CANCEL_FULFILLMENT_ENABLED=false
```

A user who has admin credentials still cannot perform those operations unless their specific gate is enabled.

### Square refunds

The admin refund form supports:

- full remaining refund when amount is blank
- partial refund when an amount is entered
- explicit reason

All refund amounts are revalidated by the backend and recorded in the audit log.

### Printful cancellation

Printful currently documents cancellation of pending/draft orders through its v1:

```
DELETE /orders/{id}
```

The project uses this endpoint intentionally because Printful's current v2 migration notes still direct cancellation to the v1 cancel operation for applicable states.

Reference:

- https://developers.printful.com/docs/
- https://developers.printful.com/docs/v2-preview/

Printful cancellation is separate from the customer's Square refund. The admin UI never assumes one action implies the other.

## Catalog management

The owner can create/edit variants with:

- BMB product
- SKU
- size
- color
- USD retail price
- Printful product ID
- Printful variant ID
- active state
- sellable state

A variant cannot be marked sellable unless:

- it is active
- price is positive
- both Printful mappings exist

The storefront only exposes active + sellable variants.

## Audit trail

Every admin mutation records:

- actor
- action
- object type
- object ID
- non-secret operational details
- timestamp

Audit records do not intentionally include card data or credentials.

## Final production checkout gates

Public transactional production mode now requires **all** of these conditions at application startup:

```
APP_ENV=production
PHASE1_API_ENABLED=true
PRODUCTION_CHECKOUT_ENABLED=true
PHASE0_5_APPROVED=true
PRODUCTION_CATALOG_APPROVED=true
PRODUCTION_CANARY_APPROVED=true

SQUARE_ENVIRONMENT=production
SQUARE_ACCESS_TOKEN=<configured>
SQUARE_LOCATION_ID=<configured>
SQUARE_WEBHOOK_SIGNATURE_KEY=<configured>
SQUARE_WEBHOOK_NOTIFICATION_URL=<configured>

PRINTFUL_MODE=production
PRINTFUL_CONFIRM_ENABLED=true
PRINTFUL_TOKEN=<configured>
PRINTFUL_STORE_ID=<configured>
PRINTFUL_WEBHOOK_SECRET_KEY=<configured>

EMAIL_MODE=smtp
SMTP_HOST=<configured>
EMAIL_FROM=<configured>

DATABASE_URL=<PostgreSQL, not SQLite>

APP_SECRET_KEY=<configured>
ADMIN_USERNAME=<configured>
ADMIN_PASSWORD=<configured>
SUPPORT_EMAIL=<configured>
```

If any prerequisite is missing, application startup fails rather than silently opening an incomplete store.

## Approval flags

### PHASE0_5_APPROVED

Set only after physical-product/sample validation.

### PRODUCTION_CATALOG_APPROVED

Set only after:

- final blank/process selected
- final Printful product/variant mappings entered
- production artwork frozen
- sellable size range approved
- retail prices approved

### PRODUCTION_CANARY_APPROVED

Set only after the controlled production canary procedure passes.

### PRODUCTION_CHECKOUT_ENABLED

Final public-store kill switch.

Keep this false until the moment public transactional launch is intended.

## Recommended launch order

1. finish sample validation
2. populate final variants in admin
3. set `PRODUCTION_CATALOG_APPROVED=true`
4. run controlled canary while public checkout remains off
5. inspect order, Square, Printful, email, tracking, refunds, reconciliation
6. set `PRODUCTION_CANARY_APPROVED=true`
7. only then set both:
   - `PHASE1_API_ENABLED=true`
   - `PRODUCTION_CHECKOUT_ENABLED=true`
8. restart application
9. run production smoke test
10. monitor `ops-report`, worker, reconciliation timer, Square, and Printful
