# Phase 1 Backend Foundation

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

This is the first transactional backend slice. It is intentionally safe to build before physical sample approval.

## Implemented

- SQLAlchemy order database
- Alembic initial schema migration
- product variant records with server-owned price and Printful mapping
- immutable order-item snapshots
- Square Checkout / Payment Links client
- Square webhook HMAC verification
- exact amount/currency verification before paid transition
- idempotent payment-event storage
- exactly-one fulfillment job per paid order
- Printful v2 draft-order client
- Printful external-ID reconciliation before draft creation
- Printful v2 webhook HMAC verification
- fulfillment lifecycle updates for order and shipment events
- retrying background worker
- customer-safe noindex order status page
- CI migration test and Phase 1 unit tests

## Safety defaults

Nothing in this branch enables a real store transaction by default.

```
PHASE1_API_ENABLED=false
PRINTFUL_MODE=disabled
PHASE0_5_APPROVED=false
SQUARE_ENVIRONMENT=sandbox
```

The foundation also **refuses to start with production checkout enabled**. A later PR must deliberately remove that block after:

- shipping calculation exists
- tax behavior is decided and tested
- physical variants/prices are approved
- Printful draft flow is proven
- live Square/Printful credentials are configured
- production canary procedure is approved

Printful `production` mode is also not capable of confirming an order in this foundation; `PrintfulClient.create_draft_order` deliberately refuses that mode.

## Sandbox flow

Once PostgreSQL (or SQLite for local development) is migrated and a test ProductVariant exists:

1. set `APP_ENV=development`
2. set `PHASE1_API_ENABLED=true`
3. configure Square Sandbox credentials/webhook
4. leave `PRINTFUL_MODE=disabled` to test Square only, or set `draft` with real Printful test-safe mappings
5. create an order through `POST /api/v1/orders`
6. create a hosted checkout link through `POST /api/v1/orders/{order_number}/square-checkout`
7. complete Square Sandbox checkout
8. verified `payment.updated` transitions the order to PAID and creates the fulfillment job
9. in Printful draft mode, the worker checks `@BMB-order-number` before creating a draft

## Important unfinished launch work

Subsequent Phase 1 increments now provide live Printful shipping quotes, Square-managed tax synchronization, refunds, transactional email jobs, and provider reconciliation.

The remaining launch work includes:

- final approved product variants/prices
- validation of Square tax configuration on the real merchant account
- production Printful confirmation
- owner/admin UI
- production transactional-email provider credentials
- production canary and rollback procedure

Production checkout and Printful confirmation remain hard-blocked until those gates pass.

## Migrations

Development:

```bash
DATABASE_URL=sqlite:///./dev.db APP_ENV=development alembic upgrade head
```

Production eventually:

```bash
alembic upgrade head
```

Do not run the Phase 1 worker against production until its environment is intentionally configured.


## Reconciliation and sandbox management

A later Phase 1 increment adds provider reconciliation and a small management CLI.

Examples:

```bash
# Development only: create a server-priced test SKU for Square Sandbox.
python -m app.manage seed-sandbox-variant \
  --product-slug lotus-of-the-void \
  --sku TEST-LOTUS-BLK-M \
  --size M \
  --price-cents 3200

# Inspect recent local order state.
python -m app.manage list-orders

# Reconcile known Square/Printful orders with provider state.
python -m app.manage reconcile
```

Sandbox seeding is explicitly refused when `APP_ENV=production`.

Square reconciliation retrieves the Square order and Payment, rechecks currency and exact amount, and can repair a missed payment webhook by transitioning the local order to PAID exactly once.

Printful reconciliation always uses the BMB order number as the provider `external_id`.
