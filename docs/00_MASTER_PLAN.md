# Master Plan

## Objective

Build `blackmetalbuddha.com` as a small, self-hosted print-on-demand store.

The customer should be able to:

1. browse products
2. select size/quantity
3. check out through PayPal
4. receive confirmation
5. have the order automatically submitted to Printful
6. receive fulfillment and tracking updates

No order should require manual transfer from PayPal to Printful.

## Launch collection

Initial designs:

1. **Lotus of the Void** — *No Self • No Fear*
2. **Dharma of Decay** — *All Things Pass*
3. **Meditate on Death** — *Emptiness Is Freedom*

## Payment decision — 2026-10-04

Use PayPal for customer payments and the same merchant PayPal account for
Printful billing. This consolidates payment administration and allows available
USD proceeds to fund fulfillment. It does not guarantee immediate availability:
held payments cannot fund Printful, and the Printful billing agreement and backup
funding must be checked.

The repository currently implements Square. This is an approved plan change,
not a completed code migration. PayPal implementation and a new live canary are
required before public checkout opens.

### Planned flow

1. BMB validates the cart, recipient, live Printful shipping and approved tax rules.
2. BMB persists a priced order and creates a PayPal Orders v2 order.
3. Customer approves payment through PayPal's supported checkout.
4. BMB captures server-side and verifies completed capture, merchant, order,
   currency and gross amount; verified webhooks/reconciliation recover missed responses.
5. BMB marks the order paid and queues Printful exactly once.
6. Printful bills the merchant separately using its configured PayPal method.

Use PayPal-hosted payment collection or eligible PayPal-hosted card components;
BMB must never receive raw card data. See [PayPal integration](03_PAYPAL_INTEGRATION.md)
and [migration tasks](superpowers/plans/2026-10-04-paypal-migration.md).

## Phase 0 — website and infrastructure

Deliver:

- DNS for `blackmetalbuddha.com`
- HTTPS
- Nginx
- application service
- PostgreSQL
- home/shop/product/cart/checkout-shell/order-status pages
- product catalog
- staging environment
- logging/backups/health checks

No real payment processing is required to exit Phase 0.

## Phase 0.5 — sample approval

Before public launch:

- select exact Printful garment blank
- configure variants
- upload final artwork
- order samples
- inspect print quality, fine detail, placement, red reproduction, fit, and wash durability
- revise artwork if needed
- photograph approved products

## Phase 1 — PayPal fiat + Printful automation

Implement:

- local BMB order state machine
- PayPal Orders v2 creation, buyer approval and server-side capture
- verified PayPal webhooks
- server-side amount verification
- idempotent PayPal order creation, capture and refund requests
- replace Square tax synchronization with approved server-side tax calculation
- Printful product/variant mapping
- Printful order creation
- signed Printful webhooks
- retry/reconciliation jobs
- transactional confirmation/tracking notifications
- refund/admin workflow

### Phase 1 exit criteria

A real order must complete:

```text
customer
  ↓
PayPal
  ↓
BMB verified paid state
  ↓
Printful
  ↓
production
  ↓
shipment
  ↓
tracking
```

with no manual copying of order data.

## Phase 2 — additional channels

After Phase 1 is stable, add marketplaces/ecommerce platforms supported by Printful.

Candidate order:

1. Etsy
2. Amazon
3. eBay
4. TikTok Shop or other channel justified by demand

Native Printful integrations should be used where they reduce operational burden.

## Phase 3 — SEO and marketing

Technical SEO begins during Phase 0.

Active acquisition starts only after checkout and fulfillment are proven.

Focus on:

- real product photography
- structured product data
- sitemap/Search Console
- product storytelling
- original content
- marketplace SEO
- social content
- paid promotion only after unit economics are known

## Future Lightning

Lightning remains outside the active implementation plan.

Revisit only when an approved provider exposes an official developer API that can:

1. initiate/accept an online Lightning payment
2. associate it with a provider/BMB order
3. expose reliable server-verifiable status/webhooks
4. automatically settle the payment to fiat/USD
5. require no manual BTC sale/conversion before Printful fulfillment

See `10_ADR_LIGHTNING_DEFERRED.md`.
