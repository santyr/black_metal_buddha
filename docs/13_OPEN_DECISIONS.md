# Open Decisions Before Public Launch

These do not block Phase 0. Updated with owner decisions from 2026-10-01.

## Confirmed product decisions

- Physical sample approved by the owner.
- Production garment: Comfort Colors 1717, Unisex Garment-Dyed Heavyweight T-Shirt.
- Launch sizes: Small, Medium, Large, XL, XXL (`S`, `M`, `L`, `XL`, `2XL`).
- Variant SKU convention and reservations: `25_PRODUCT_SKUS.md`.

## Product

- final art after samples
- print technique
- retail price

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

- valid approved Dzogchen-A logo still needed: both assets in remote commit `a33277d` fail decoding
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
