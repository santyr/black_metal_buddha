# Coding Agent Handoff

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## Mission

Migrate the existing Phase 1 Square implementation to PayPal using [the implementation plan](superpowers/plans/2026-10-04-paypal-migration.md). Phase 0 already exists.

Repository:

```text
santyr/black_metal_buddha
```

Domain:

```text
blackmetalbuddha.com
```

## Architecture

- self-hosted BMB storefront/order service
- PayPal Orders v2 checkout and capture
- verified PayPal webhooks
- local BMB database
- automatic Printful fulfillment
- no LNbits
- no Strike
- no Lightning implementation

## Read first

1. `00_MASTER_PLAN.md`
2. `01_ARCHITECTURE.md`
3. `02_DATA_MODEL.md`
4. `03_PAYPAL_INTEGRATION.md`
5. `04_PRINTFUL_INTEGRATION.md`
6. `05_PHASE0_VPS_DEPLOYMENT.md`
7. `06_SECURITY_PRIVACY.md`
8. `07_TESTING_AND_RELEASE.md`
9. `10_ADR_LIGHTNING_DEFERRED.md`

## First milestone

Staging flow:

```text
one SKU
  ↓
local cart/order
  ↓
PayPal Sandbox order
  ↓
PayPal-hosted checkout
  ↓
server-side capture + verified payment webhook
  ↓
BMB PAID
  ↓
mocked Printful fulfillment (staging writes disabled)
```

No production Printful fulfillment until explicitly enabled by the release plan.

## Rules

- server controls all totals
- browser return is never proof of payment
- verify PayPal webhooks
- persist operation-specific PayPal-Request-Id values
- require completed capture, not buyer approval
- preserve historical Square payment/refund records
- replace Square tax synchronization before live checkout
- use Printful `external_id`
- verify Printful webhooks
- duplicate events must be harmless
- no undocumented PayPal APIs
- no Lightning code until ADR-001 is reopened
