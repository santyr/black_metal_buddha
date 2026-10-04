# Phase 1 — Customer Checkout UI

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

The storefront now has two operating modes.

## Preview mode

Default production state while launch gates remain closed:

```
PHASE1_API_ENABLED=false
```

Behavior:

- product art and descriptions remain public
- no sellable variants or prices are exposed
- cart remains a local preview list
- `/checkout` returns 404
- no customer data is collected
- no Square or Printful calls occur

## Transactional staging mode

When Phase 1 is intentionally enabled in a non-production environment and sellable variants exist:

- product pages query the server-side variant table
- size/color/price are displayed from the database
- cart stores SKU, size, color, quantity, and a display-only price snapshot
- checkout sends **SKU + quantity only** as merchandise authority
- server recalculates the cart from current sellable variant records
- buyer enters shipping information
- BMB queries current Printful shipping rates
- buyer selects a shipping-method identifier
- BMB re-queries/validates the selected rate
- BMB creates the Square hosted checkout
- Square applies configured tax rules
- BMB validates and stores the Square-calculated tax/total
- browser redirects to Square

The browser never supplies an authoritative merchandise price, shipping price, tax, discount, or total.

## Customer data

Shipping information is not stored in browser localStorage.

It is submitted directly to the BMB order API and persisted only in the backend order record needed for fulfillment.

The public order-status page intentionally omits buyer email and postal address.

Public order numbers use 80 bits of random hexadecimal data:

```
BMB-XXXXXXXXXXXXXXXXXXXX
```

## Cart completion

The browser remembers the active order number only in `sessionStorage` immediately before redirecting to Square.

When the customer returns to the matching order-status page and the server reports payment `COMPLETED`, that specific checkout cart is cleared.

Revisiting an unrelated/old completed order does not clear a new cart.

## SEO

When real sellable variants are available, product JSON-LD gains an `AggregateOffer` with:

- currency
- low price
- high price
- offer count
- in-stock availability

No price/Offer markup is emitted while the site is in preview mode.

Utility URLs remain excluded from search indexing:

- `/cart`
- `/checkout`
- `/orders/`
- `/admin`
- `/api/`
