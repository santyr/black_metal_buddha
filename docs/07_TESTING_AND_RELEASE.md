# Testing and Release

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## PayPal tests

Use PayPal Sandbox.

Test:

- order creation
- idempotent retry
- successful completed capture (approval alone is not paid)
- pending/denied capture and reversal
- wrong merchant or order binding
- capture succeeds remotely but response is lost
- tax and shipping breakdown mismatch
- declined/abandoned checkout
- duplicate webhook
- invalid webhook signature
- webhook before customer returns
- customer never returns
- amount mismatch
- currency mismatch
- delayed webhook
- reconciliation repair

## Printful tests

Staging uses mocks for writes and read-only access to the existing Printful store. Draft creation is not a payment sandbox. Exercise the following with mocks; actual writes/confirmation require the controlled live order:

- create draft
- confirm
- duplicate external ID
- timeout after create
- failed/held state
- duplicate webhook
- shipment update

## Critical invariant

A customer returning from PayPal must never be enough to mark an order paid.

Only a verified completed capture bound to the expected merchant, order, USD currency and gross amount can do that.

## Production canary

1. place one real order
2. verify PayPal order/capture IDs
3. verify PayPal capture `COMPLETED`
4. verify BMB order `PAID`
5. verify exactly one Printful order
6. verify production
7. verify shipment/tracking
8. verify reconciliation

## Launch gate

- [ ] physical samples approved
- [ ] PayPal production canary
- [ ] Printful production canary
- [ ] refund flow
- [ ] duplicate protections
- [ ] failed fulfillment alert
- [ ] backup restore
- [ ] policies
- [ ] mobile checkout
- [ ] accessibility smoke test
