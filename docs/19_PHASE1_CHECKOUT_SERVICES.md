# Phase 1 — Sandbox Checkout, Shipping, Tax, Refunds, and Email

This increment extends the Phase 1 backend foundation while retaining the hard production block.

## Shipping

BMB uses Printful's **v2 Shipping Rates API** immediately before checkout.

The server sends:

- recipient address
- blank catalog variant IDs resolved from the saved Printful sync variants
- requested currency

and receives the currently available shipping methods and rates.

The saved sync variant ID is resolved with `GET /store/variants/{id}` and its
saved product relationship is checked. The v2 rate request uses
`source=catalog` and `catalog_variant_id`; saved sync IDs are not blank IDs.

A buyer cannot submit an arbitrary shipping price. The browser can only select a shipping-method identifier; BMB re-queries Printful and stores the matching server-returned rate.

Shipping quotes expire before Square checkout. The current guard is **15 minutes**, intentionally much shorter than the possible rate-change window.

Reference:

- https://developers.printful.com/docs/v2-beta/
- https://developers.printful.com/docs/#tag/Products-API

## Address ownership

BMB owns the shipping address used to obtain the Printful quote.

Square checkout receives the same address as the order's `SHIPMENT` fulfillment. Square's editable shipping-address prompt is disabled so the buyer cannot change destination after Printful shipping has been quoted.

## Square taxes

The Square order uses:

```json
{
  "pricing_options": {
    "auto_apply_taxes": true
  }
}
```

Square therefore applies the tax configuration/rules available to the connected Square merchant.

BMB does **not** maintain its own sales-tax-rate table.

Before accepting the Square total, BMB retrieves the generated Square order and validates:

- BMB order reference
- number of line items
- item names
- quantities
- exact unit prices
- shipping/service charge
- discount amount
- currency

Only after those checks does BMB copy Square's calculated tax and total into its order.

The same validation is run during provider reconciliation.

### Production tax gate

This integration still requires validation against the real Square merchant's sales-tax configuration before the production checkout block can be removed.

Square's own documentation notes that merchants remain responsible for configuring applicable tax collection correctly.

References:

- https://developer.squareup.com/docs/orders-api/apply-taxes-and-discounts/auto-apply-taxes
- https://squareup.com/help/us/en/article/5061-create-and-manage-your-tax-settings

## Refunds

Refunds use Square's `POST /v2/refunds` endpoint.

The local refund model records:

- Square refund ID
- local order ID
- amount
- currency
- status
- reason

The current management command is deliberately **Square Sandbox only**:

```bash
python -m app.manage refund-order BMB-... --amount-cents 1000 --reason "Sandbox test"
```

Square refund webhooks update the durable local refund state. Completed refunds enqueue a transactional refund-confirmation email.

Reference:

- https://developer.squareup.com/reference/square/refunds/refund-payment

## Transactional email

Email jobs are durable DB jobs and use one of:

```
EMAIL_MODE=disabled
EMAIL_MODE=console
EMAIL_MODE=smtp
```

SMTP mode uses STARTTLS and requires:

```
SMTP_HOST
SMTP_PORT
EMAIL_FROM
```

Credentials are optional only when the selected SMTP relay does not require login.

Current customer notifications:

- payment/order confirmation
- shipment notification
- completed refund notification

When email is disabled, jobs remain pending rather than being silently discarded.

## End-to-end sandbox harness

After the database is migrated and a sandbox SKU exists:

```bash
APP_ENV=development \
PHASE1_API_ENABLED=true \
SQUARE_ENVIRONMENT=sandbox \
PRINTFUL_MODE=draft \
python -m app.manage sandbox-checkout \
  --sku TEST-LOTUS-BLK-M \
  --name "Test Buyer" \
  --email test@example.com \
  --address1 "1 Test Way" \
  --city Denver \
  --state CO \
  --postal-code 80202
```

The command:

1. creates the local order
2. retrieves current Printful shipping rates
3. selects the requested shipping method (default `STANDARD`)
4. creates the Square Sandbox payment link
5. retrieves the generated Square order
6. validates BMB line items/shipping
7. copies Square tax and total into BMB
8. prints the hosted checkout URL

After paying the Sandbox checkout:

```bash
python -m app.manage reconcile
python -m app.manage list-orders
```

The payment webhook or reconciliation process should transition the order to `PAID`, enqueue the Printful draft and confirmation email jobs, and the worker should create at most one Printful order with the BMB order number as `external_id`.

## Still blocked

Production checkout remains explicitly disabled in code.

Production Printful confirmation remains explicitly unavailable.

Removal of those blocks still requires:

- Phase 0.5 physical sample approval
- final Printful SKU mappings
- approved retail pricing
- tax behavior validated on the merchant account
- live shipping quote validation
- refund canary
- transactional email provider configured
- full production canary
