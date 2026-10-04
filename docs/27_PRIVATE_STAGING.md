# Private staging

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).

> The Square-specific details below describe the existing implementation/history, not the new launch target. Replace provider-specific procedures during migration before using them to launch PayPal.

Staging uses a separate application source snapshot, service account and
database. It is available privately; production customer data and settings
are not copied into it. Deployment details and installation records belong
in the private launch handoff.

## Shared Printful store

The owner reports that the current Printful plan allows one store. Staging
uses the existing store for catalog reads and previews. A second Printful
store is no longer required.

1. Create a separate store-scoped token restricted to saved product/catalog
   reads in Printful's Developer Portal. Supply it through the private staging
   settings, using the existing store ID. Do not reuse the production token.
2. Enable catalog synchronization only after read-only access is verified.
   Keep `PRINTFUL_MODE=disabled` and `PRINTFUL_CONFIRM_ENABLED=false`.
   Catalog synchronization works independently of fulfillment mode.
3. Do not edit or delete shared products, create or confirm orders, or change
   the shared store's production webhook subscriptions from staging.

The API should be used for supported work. Store and private-token creation
require Printful's dashboard or Developer Portal. A draft Printful order is
not a separate billing sandbox.

## Square and email

- Use separate Square Sandbox credentials and location for staging payments.
  Keep the production merchant credentials out of staging.
- Use fixture events for staging fulfillment handling. These checks do not
  establish production Printful callback delivery or fulfillment readiness.
- Keep staging email disabled until a designated staging delivery setup is
  supplied. Sending a real email requires approval of the message and recipient.
- Keep checkout and owner-console activation gates closed until their
  prerequisites and the requested activation are satisfied.

## Current readiness

The private staging service is running, but staging provider credentials have
not been supplied. Its catalog is not yet connected to the shared Printful
store. Existing disabled catalog rows do not prove current product readiness.

The owner still needs to provide read-only Printful access, Square Sandbox
access and the staging hostname/DNS decision through the private handoff.
Public HTTPS and signed Square callbacks must be verified before relying on
staging payment results.

Refresh staging from the reviewed release before validating a deployment.
Verify its source, health, database isolation and provider gates against the
actual running instance.

## Production verification

Actual Square production payment, Printful order submission and billing,
provider callbacks, customer email delivery, shipment tracking and refund
reconciliation must be verified in the approved controlled production order.
Staging results do not replace that order or authorize a charge.

Follow [the launch input handoff](28_LAUNCH_INPUT_HANDOFF.md) for account steps,
owner decisions and the controlled order approval sequence.
