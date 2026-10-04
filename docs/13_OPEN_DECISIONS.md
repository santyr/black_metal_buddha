# Open Decisions Before Public Launch

These do not block Phase 0. Payment decision updated 2026-10-04; older non-payment items below may be superseded by the launch handoff.
See [the step-by-step launch handoff](28_LAUNCH_INPUT_HANDOFF.md) for account setup and required inputs.

## Payment decision and remaining launch gates

- PayPal replaces Square for customer checkout; PayPal also funds Printful billing.
- Implement and validate the migration before accepting public payments.
- Verify PayPal Business/card eligibility, separate sandbox/live app credentials and webhook IDs.
- Replace Square tax calculation with an owner-approved approach for USD sales to the United States and Canada. Missing tax configuration must block launch.
- Confirm funding behavior, backup funding, capture/refund reconciliation and a new live canary.
- Pay with Crypto is optional and approval-gated; Lightning remains deferred.

## Confirmed product decisions

- Physical sample approved by the owner.
- Production garment: Comfort Colors 1717, Unisex Garment-Dyed Heavyweight T-Shirt.
- Launch sizes: Small, Medium, Large, XL, XXL (`S`, `M`, `L`, `XL`, `2XL`).
- Variant SKU convention and reservations: `25_PRODUCT_SKUS.md`.
- Retail price: $35.00 USD per shirt in every launch size, plus shipping.
- Corrected approved WebP logo received and fully decoded.

## Product

- final art after samples
- print technique

## Shipping

- US-only or international
- flat vs calculated
- free-shipping threshold
- delivery estimate wording

## Tax

Choose the tax-calculation/collection approach after appropriate accounting/tax review. Do not encode assumptions.

## Returns

Define:

- defect/misprint
- buyer remorse
- wrong size
- bad address
- lost shipment

## Email

Choose transactional email service.

Messages:

- order confirmation
- action-required problem
- shipped/tracking
- refund

## Branding

- favicon
- color/type system
- commercial font licensing
- Printful packing-slip branding

## Infrastructure

- exact VPS host
- existing Nginx conventions
- certificate workflow
- backup destination
- staging hostname
- repository location
