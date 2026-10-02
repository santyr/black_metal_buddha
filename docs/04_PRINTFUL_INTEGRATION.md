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

The checkout total must be deterministic before Square is charged.

Choose one:

1. flat shipping rules maintained by BMB
2. server-side Printful rate estimation before Square payment-link creation

If real-time Printful shipping rates require customer address before checkout creation, collect shipping in BMB before sending the buyer to Square.

## Printful billing

A customer can successfully pay Square while Printful billing later fails.

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
