# Security and Privacy

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## Payment handling

PayPal hosts payment collection, including hosted card components if needed. Do not store or proxy raw card information.

## Webhooks

### PayPal

Verify PayPal webhooks using its official verification API and the environment-specific configured webhook ID. Fail closed on verification failure; retry verification outages without marking orders paid. A webhook ID is not a shared signing secret. Never copy Square's HMAC algorithm.

### Printful

Verify the current Printful signed-webhook format before processing.

## Idempotency

Database constraints and provider idempotency must prevent:

- duplicate checkout/order-creation operations
- duplicate payment processing
- duplicate Printful orders
- repeated customer notifications

## PII

Store only what fulfillment requires. Avoid unnecessary customer profiles and do not routinely log full shipping details.

## Secrets

Never expose or commit:

- PayPal access token
- PayPal client secret and OAuth access tokens
- Printful token
- application secret
- DB credentials

## Application

- CSRF protection
- secure cookies
- rate limiting where useful
- trusted server-side totals
- quantity limits
- restrictive security headers
- safe error handling

## Server

- SSH keys
- non-root service
- firewall
- non-public DB
- timely security updates
- off-host backups
