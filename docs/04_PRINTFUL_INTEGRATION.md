# Printful Integration

## Objective

Once BMB has a verified paid order, Printful fulfillment must happen automatically.

Customer payment method is irrelevant to Printful. Printful receives a paid BMB order and fulfills it using the merchant's configured Printful billing source.

## Authentication

Use a private Printful token for the BMB store. Keep it server-side.

## Catalog

For each BMB SKU store a stable Printful mapping.

The database's `printful_product_id` and `printful_variant_id` contain saved
sync product/variant IDs. v1 order requests use `sync_variant_id` to inherit the
saved artwork/placement. v2 shipping requests first resolve the saved variant
with `GET /store/variants/{id}` and send its blank `catalog_variant_id`.
Do not interchange these two ID namespaces.

Verify before launch:

- product active
- exact blank
- exact size
- exact black color
- artwork
- placement
- cost
- shipping behavior

## Submission flow

```text
BMB order = PAID
      ↓
SUBMIT_PRINTFUL_ORDER job
      ↓
lookup Printful @external_id
      ↓
already exists?
  ├─ yes -> reconcile
  └─ no  -> create order
      ↓
confirm order
      ↓
store Printful order ID/status
```

Use:

```text
Printful external_id = BMB order number
```

## Webhooks

Use signed Printful webhooks according to the current API version. Verify signatures before state changes.

Track relevant:

- order state
- hold/review
- failure
- shipment
- tracking
- return

## Shipping

The checkout total must be deterministic before PayPal is charged.

Use the approved live Printful quote, collected after BMB validates the recipient and before creating the PayPal order. Lock recipient and totals for that payment attempt; changed addresses require a fresh quote and checkout.

## Printful billing

Owner decision (2026-10-04): use the configured merchant PayPal account for Printful billing and customer receipts. Check the Printful automatic-payment agreement uses available balance as intended; retain backup funding or a funded Printful Wallet for holds and timing gaps. Do not implement automatic transfers or crypto conversion as part of the BMB application.

A customer can successfully pay PayPal while Printful billing later fails.

Therefore alert on:

```text
BMB PAID
+
Printful billing/order submission failure
```

This is a high-priority operational state.

## Reconciliation

Find:

- paid BMB orders with no Printful order
- Printful failed orders
- Printful holds
- shipped Printful orders not updated locally
- missing tracking
