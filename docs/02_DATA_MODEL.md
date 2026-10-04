# Data Model

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


Keep the schema small and auditable.

## products

```text
id
slug
name
subtitle
description
active
created_at
updated_at
```

## product_variants

```text
id
product_id
sku
size
color
retail_price_cents
currency
active
printful_variant_id
printful_external_variant_id
created_at
updated_at
```

## product_media

```text
id
product_id
kind
path_or_url
alt_text
sort_order
```

## orders

```text
id
order_number
email
customer_name
phone_optional
ship_address1
ship_address2
ship_city
ship_state
ship_postal_code
ship_country
currency
subtotal_cents
discount_cents
shipping_cents
tax_cents
total_cents
payment_state
fulfillment_state
order_state
payment_provider
paypal_order_id
paypal_capture_id
printful_order_id
printful_external_id
created_at
paid_at
submitted_to_printful_at
shipped_at
updated_at
```

## order_items

Store snapshots so old orders do not change when catalog data changes.

```text
id
order_id
product_variant_id
sku_snapshot
name_snapshot
size_snapshot
color_snapshot
unit_price_cents
quantity
line_total_cents
printful_variant_id_snapshot
```

## Migration compatibility

Add PayPal order/capture/refund identifiers and a provider discriminator with unique constraints. Preserve existing Square columns and historical IDs; never relabel Square records as PayPal. Refunds and reconciliation must dispatch by the recorded provider. Add durable request IDs for create, capture and refund retries.

## payment_events

```text
id
provider
provider_event_id
provider_payment_id
event_type
event_time
payload_hash
processed_at
processing_result
```

Unique: `(provider, provider_event_id)`.

## fulfillment_events

```text
id
provider
provider_event_id_or_hash
provider_order_id
event_type
event_time
payload_hash
processed_at
processing_result
```

## jobs

```text
id
job_type
order_id
state
attempt_count
next_attempt_at
last_error
locked_at
created_at
updated_at
```

Initial job types:

- `SUBMIT_PRINTFUL_ORDER`
- `CONFIRM_PRINTFUL_ORDER`
- `SEND_ORDER_CONFIRMATION`
- `SEND_SHIPPING_NOTIFICATION`
- `RECONCILE_ORDER`

## Money

Use integer cents internally.

```text
$40.00 -> 4000
```

Never use binary floating-point for financial totals.
