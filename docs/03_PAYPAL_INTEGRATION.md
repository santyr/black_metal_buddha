# PayPal Integration — approved target, 2026-10-04

## Decision and scope

Replace Square with PayPal for new customer checkouts. Use the same PayPal
Business account already configured for Printful billing. Keep the self-hosted
BMB storefront, catalog, order database and direct Printful integration.

This document specifies the target. Production checkout remains closed;
[the migration plan](superpowers/plans/2026-10-04-paypal-migration.md) must be
implemented and validated before launch. Existing Square records remain intact.

## Checkout contract

- USD checkout; approved shipping destinations remain United States and Canada.
- BMB collects and validates recipient details and live Printful shipping first.
- Calculate merchandise, shipping and approved tax server-side; freeze the order
  snapshot for each attempt. Use integer cents, converting exactly to PayPal's
  decimal amount strings. Do not treat processing fees as a reduction in the
  gross amount that must match the customer order.
- Replace Square-derived taxes explicitly. PayPal order amounts are not a tax
  calculation service. Missing approved tax configuration blocks production;
  zero tax is allowed only when the approved rules produce zero.
- Create a single-purchase-unit Orders v2 order with CAPTURE intent for ordinary
  PayPal/card checkout. Bind it to the BMB reference, expected merchant and shipping
  snapshot. Persist the provider order ID and returned approval URL.
- Redirect the buyer to supported PayPal payment collection. Verify card/guest
  checkout eligibility in the merchant account; use eligible PayPal-hosted card
  fields if needed. Never proxy raw card details through BMB.
- Buyer approval/return is not payment. Capture through the server, using the stored
  PayPal order ID and a persistent request ID. An authenticated return may initiate
  capture, but only PayPal's verified completed capture establishes payment.
- Enforce one active attempt per local order. Shipping/address changes require
  requoting and a new attempt; never fulfill an address different from the paid
  snapshot without an explicit reviewed correction process.

### Approved quote policy (owner decision, 2026-10-04)

Charge $35/current trusted catalog merchandise prices, live shipping and
Printful's quoted tax separately. Use a complete `/orders/estimate-costs`
response's `costs.tax + costs.vat`, preserving the response and timestamp.
Do not substitute a local flat rate, estimate an unknown tax as zero, or pass
supplier fees off as tax. Configuration defaults closed; enable
`CHECKOUT_TAX_MODE=printful_quote` and `CHECKOUT_TAX_POLICY_APPROVED=true` only
for the approved setup. Explicit complete zero-tax quotes are valid for US/CA.

BMB is in Fremont County, Colorado; no resale certificates are held or planned.
The owner reports accountant advice on Printful collection and their filing
approach. This records the owner's guidance and checkout instruction without
asserting an independent legal conclusion about returns or remittance.

## Capture, webhooks and reconciliation

Create/capture/refund each have their own durable `PayPal-Request-Id`. Retry an
uncertain operation with its original key; never generate a new key just because
of a timeout. Observe documented retention limits and reconcile before retrying
an operation whose outcome is unknown.

Use `/api/phase1/webhooks/paypal` as the planned listener. Verify real app webhooks
with PayPal's official verification API and configured environment-specific
webhook ID. Verification outages are retryable; unverified events cannot mutate
payment state. Do not reuse Square signature code. Sandbox simulator delivery
alone does not prove actual app webhook verification.

Handle approved orders by scheduling an idempotent capture attempt, so a buyer
closing the browser cannot strand an approved payment. Capture completion,
pending, denial, refund and reversal events must be reconciled to authoritative
provider records. Subscribe to the exact supported event names when implementing.

Before marking paid, verify the completed capture's identity, related PayPal
order, BMB reference, expected payee, USD currency and full gross amount. Deduplicate
by provider/event and capture ID. Atomically record payment and enqueue one
Printful submission. Pending or approved states cannot trigger production.
Late events must not regress a refunded/reversed order to paid.

Reconciliation repairs missed webhooks and lost capture responses, including
approved-but-not-captured orders, pending captures, refunds and paid orders
missing fulfillment work. Alerts expose capture failures and payment reversals.

## Printful billing and cash availability

Customer payment and supplier billing remain separate transactions. Available
PayPal USD receipts may cover Printful through its automatic-payment agreement;
verify that agreement's funding preference. Funds can be held or unavailable.
Maintain a suitable backup source or funded Printful Wallet. A completed capture
does not prove funds are spendable or that Printful billing succeeded.

Preserve existing Printful external-ID deduplication, cost checks and confirmation
gates. A paid order with failed supplier billing enters an actionable hold/failure
workflow: reconcile the supplier order before retrying and never charge the buyer
again to retry fulfillment.

## Refunds and history

Refund PayPal captures through the Payments API, with durable request IDs and
local pending/completed/failed tracking. Preserve partial-refund limits and prevent
concurrent over-refunds. Customer refunds and Printful cancellations/refunds are
separate operations; do not promise cancellation once production has started.

Keep Square order/payment/refund identifiers for historical records. Route legacy
refunds and reconciliation to Square only for those records, if any exist. Stop
creating new Square checkouts at cutover; retire legacy credentials/listeners only
after outstanding records are settled and the retention requirements are met.

## Bitcoin and Lightning

PayPal documents Pay with Crypto, including Bitcoin-funded payments converted to
USD for eligible US merchants. Treat it as an optional post-core-checkout phase:
verify Expanded Checkout approval, integration eligibility and supported wallets.
Its documented automatic-capture flow differs from ordinary approval-then-capture;
use the dedicated documented flow rather than blindly reusing the card sequence.
Test settlement and refunds (which may return stablecoins to buyers), and disclose
the actual refund behavior before enabling it.

Native Lightning invoice/LNURL support is not established by the reviewed PayPal
documentation. Keep [ADR-001](10_ADR_LIGHTNING_DEFERRED.md) in force. No additional
crypto processor, manual conversion or Lightning discount is part of this migration.

## Sources

Reviewed 2026-10-04; recheck exact API fields and eligibility during implementation.

- [Orders v2](https://developer.paypal.com/docs/api/orders/v2/)
- [Payments v2](https://developer.paypal.com/docs/api/payments/v2/)
- [Webhook verification](https://developer.paypal.com/api/rest/webhooks/rest/)
- [Idempotency](https://developer.paypal.com/api/rest/reference/idempotency/)
- [Pay with Crypto eligibility](https://www.paypal.com/us/cshelp/article/what-is-pay-with-crypto-help1236)
- [Crypto integration](https://developer.paypal.com/crypto/)
- [Automatic-payment funding](https://www.paypal.com/webapps/mpp/popup/about-payment-methods)
- [Payment holds](https://www.paypal.com/us/cshelp/article/why-is-my-payment-on-hold-or-unavailable-help126)
- [Printful billing](https://help.printful.com/hc/en-us/articles/50264607936785-How-does-the-Printful-billing-system-work)
