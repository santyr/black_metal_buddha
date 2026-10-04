# Phase 0 — VPS Deployment

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## Domain

Canonical:

```text
https://blackmetalbuddha.com
```

Redirect `www`.

## Runtime

Recommended:

- Nginx
- FastAPI
- PostgreSQL
- systemd

Example app bind:

```text
127.0.0.1:8088
```

Only Nginx is internet-facing for the app.

## Example filesystem

```text
/opt/blackmetalbuddha/
/etc/blackmetalbuddha/blackmetalbuddha.env
/var/lib/blackmetalbuddha/
/var/log/blackmetalbuddha/
```

Run under a dedicated non-root account.

## Staging

Prefer:

```text
staging.blackmetalbuddha.com
```

Use:

- separate DB
- PayPal Sandbox
- test-safe Printful behavior

Protect staging from public indexing/access.

## Planned secrets/config (not yet implemented)

```text
DATABASE_URL
APP_SECRET_KEY
PUBLIC_BASE_URL

PAYPAL_ENVIRONMENT
PAYPAL_CLIENT_ID
PAYPAL_CLIENT_SECRET
PAYPAL_MERCHANT_ID
PAYPAL_WEBHOOK_ID
PAYPAL_WEBHOOK_NOTIFICATION_URL

PRINTFUL_TOKEN
PRINTFUL_STORE_ID
PRINTFUL_WEBHOOK_SECRET_KEY

MAIL SETTINGS
```

No LNbits/Strike configuration is part of BMB.

## Backups

- nightly PostgreSQL dump
- encrypted off-host copy
- artwork backup
- restore test
- deployment rollback procedure
