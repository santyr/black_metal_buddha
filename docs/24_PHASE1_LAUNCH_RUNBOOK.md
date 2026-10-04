# Phase 1 — Launch Readiness & Production Canary

PayPal is implemented on the migration branch. Production checkout stays closed
until the app-specific sandbox checks, backup restoration and controlled live
order are verified. All physical samples are approved.

This document is the final software-side launch procedure.

The store is still not authorized for public transactions until the physical-product gate and live canary pass.

## 1. Validate and archive the launch catalog

After sample approval, review the final variants in Printful. With
`PRINTFUL_CATALOG_SYNC_ENABLED=true`, the complete published Printful catalog
supplies the storefront; wait for a successful sync before validating. Use the
manual import instructions below only when automatic Printful sync is disabled.

Validate:

```bash
python -m app.manage catalog-validate
```

Export an archival manifest:

```bash
python -m app.manage catalog-export /secure/path/bmb-launch-catalog.json
```

The command prints the deterministic sellable-catalog SHA-256 fingerprint.

Set that exact value as:

```
PRODUCTION_CATALOG_FINGERPRINT=<sha256>
PRODUCTION_CATALOG_APPROVED=true
```

The fingerprint covers sellable SKU, product, size, color, price, active/sellable state, and Printful mappings.

The controlled canary verifies the archived fingerprint against the current
catalog before creating checkout. Review and archive a new fingerprint if the
catalog changes before that order.

At public production startup, automatic Printful mode checks that the imported
catalog belongs to the configured store. Subsequent complete snapshots continue
to update products, prices and availability; new checkout and pending payment
links require a fresh catalog and valid current variants. The archived launch
fingerprint remains a launch prerequisite, but it does not freeze future
Printful edits.

When automatic sync is disabled, production startup validates the catalog and
compares its current fingerprint to `PRODUCTION_CATALOG_FINGERPRINT`, refusing
startup if it differs. Website admin catalog writes are blocked while public
checkout is enabled. With automatic sync enabled, manage products in Printful.

### Catalog import

Dry run:

```bash
python -m app.manage catalog-import bmb-launch-catalog.json
```

Apply:

```bash
python -m app.manage catalog-import bmb-launch-catalog.json --apply
```

Imports are transactional: an invalid resulting catalog rolls back.

---

# 2. Prepare production with public checkout OFF

Keep:

```
PHASE1_API_ENABLED=false
PRODUCTION_CHECKOUT_ENABLED=false
PAYPAL_PRODUCTION_CANARY_APPROVED=false
PRODUCTION_CANARY_MODE=true
```

Canary prerequisites:

```
APP_ENV=production
PHASE0_5_APPROVED=true
PRODUCTION_CATALOG_APPROVED=true
PRODUCTION_CATALOG_FINGERPRINT=<approved sha256>

PAYPAL_ENVIRONMENT=production
PAYPAL_CLIENT_ID=<live app client ID>
PAYPAL_CLIENT_SECRET=<private live secret>
PAYPAL_MERCHANT_ID=<verified merchant>
PAYPAL_WEBHOOK_ID=<live app webhook ID>
PAYPAL_WEBHOOK_NOTIFICATION_URL=https://blackmetalbuddha.com/api/phase1/webhooks/paypal
CHECKOUT_TAX_MODE=printful_quote
CHECKOUT_TAX_POLICY_APPROVED=true

PRINTFUL_MODE=production
PRINTFUL_CONFIRM_ENABLED=true
live Printful credentials

EMAIL_MODE=smtp
working SMTP configuration

PostgreSQL DATABASE_URL
SUPPORT_EMAIL
```

The public checkout route remains hidden while the webhook, worker, admin, and canary paths remain usable.

---

# 3. Run one controlled live canary

The canary is a **real PayPal transaction and a real chargeable Printful fulfillment**.

Use the owner/test recipient and one approved SKU.

Example:

```bash
python -m app.manage production-canary \
  --i-understand-this-is-live \
  --sku BMB-LOTUS-CC1717-BLK-M \
  --quantity 1 \
  --shipping STANDARD \
  --name "Owner Name" \
  --email owner@example.com \
  --address1 "..." \
  --city "..." \
  --state CO \
  --postal-code "..."
```

Without `--i-understand-this-is-live`, the command refuses to create the production checkout.

Use an actual SKU from the latest imported catalog in place of the example. It must
have an approved price and actual Printful mappings and be active and sellable
before running the canary; reserving the SKU alone does not satisfy these gates.

The command:

1. revalidates production canary settings
2. validates exact catalog fingerprint
3. creates a DB order marked `is_canary=true`
4. obtains current live Printful shipping
5. creates the live PayPal checkout
6. quotes actual Printful tax/VAT and freezes pricing, address and request key
7. prints the hosted PayPal checkout URL

Pay the checkout yourself.

Verified PayPal webhooks queue authoritative capture; only a completed matching capture marks the order paid. The worker creates/reuses the Printful draft, verifies costs, and confirms production exactly once.

During the canary, public checkout remains off.

The marked canary order-status page is allowed even while public checkout is off.

---

# 4. Verify the canary

Run:

```bash
python -m app.manage canary-status BMB-...
```

Exit 0 requires:

- PayPal payment completed
- Printful confirmation recorded
- Printful cost known
- Printful cost <= retail order total
- no failed jobs
- order-confirmation email job completed
- fulfillment moved into an accepted post-confirmation state

Exit 2 means the canary is not ready for approval.

Also verify manually:

- PayPal Dashboard payment
- tax amount
- shipping amount
- BMB admin order state
- actual confirmation email
- Printful order and charge
- Printful production state
- shipment webhook
- tracking email
- order-status tracking page
- reconciliation after temporarily simulating/missing a webhook if practical
- PayPal refund canary if refund behavior has not already been verified

Once fully satisfied:

```
PAYPAL_PRODUCTION_CANARY_APPROVED=true
PRODUCTION_CANARY_MODE=false
```

Do not mark canary approved merely because payment succeeded.

---

# 5. PostgreSQL backup before launch

Install/enable:

```bash
sudo cp deploy/systemd/blackmetalbuddha-backup.service /etc/systemd/system/
sudo cp deploy/systemd/blackmetalbuddha-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blackmetalbuddha-backup.timer
```

Manual backup:

```bash
sudo systemctl start blackmetalbuddha-backup.service
sudo journalctl -u blackmetalbuddha-backup.service -n 50
```

Default:

```
/var/backups/blackmetalbuddha
30-day local retention
custom-format pg_dump
SHA-256 sidecar
```

A local backup is not sufficient by itself. Copy backups to an encrypted off-host destination using the VPS's normal backup process.

## Restore test

Use a disposable/test PostgreSQL database only:

```bash
export BMB_RESTORE_TEST_DATABASE_URL='postgresql://.../blackmetalbuddha_restore_test'
export BMB_ALLOW_RESTORE_TEST=true
bash deploy/verify-backup.sh /var/backups/blackmetalbuddha/blackmetalbuddha-....dump
```

The command refuses without the explicit live-cost acknowledgment. Review the exact merchandise/shipping/tax total before paying; payment and Printful confirmation incur real charges.

---

# 6. Enable public checkout

Only after all launch gates pass:

```
APP_ENV=production
PHASE1_API_ENABLED=true
PRODUCTION_CHECKOUT_ENABLED=true
PAYPAL_PRODUCTION_CANARY_APPROVED=true
PRODUCTION_CATALOG_APPROVED=true
PHASE0_5_APPROVED=true
```

All other live PayPal, Printful, SMTP, PostgreSQL, admin, support-contact, and fingerprint prerequisites must also remain configured.

Restart:

```bash
sudo systemctl restart blackmetalbuddha.service
sudo systemctl restart blackmetalbuddha-worker.service
```

If startup refuses, **fix the failed gate**. Do not bypass validation.

---

# 7. Public Phase 1 smoke test

Run:

```bash
bash deploy/phase1-smoke-test.sh https://blackmetalbuddha.com
```

It validates:

- health
- nonempty public sellable catalog
- checkout route
- unauthenticated admin protection
- robots exclusions
- core security headers

It deliberately does not place a real transaction. The live canary is the transaction test.

---

# 8. Initial launch monitoring

Keep these running:

```
blackmetalbuddha.service
blackmetalbuddha-worker.service
blackmetalbuddha-reconcile.timer
blackmetalbuddha-backup.timer
```

Inspect:

```bash
systemctl status blackmetalbuddha.service blackmetalbuddha-worker.service
systemctl list-timers 'blackmetalbuddha-*'
python -m app.manage ops-report --json
```

For automated monitoring:

```bash
python -m app.manage ops-report --json --fail-on-attention
```

Exit 2 means owner attention is required.

---

# 9. Emergency stop

The fastest storefront kill switch is:

```
PHASE1_API_ENABLED=false
PRODUCTION_CHECKOUT_ENABLED=false
```

Restart the web application.

This immediately returns the public site to preview mode while preserving orders, worker state, reconciliation, admin access, and provider records.

To prevent any new Printful confirmation as well:

```
PRINTFUL_CONFIRM_ENABLED=false
PRINTFUL_MODE=disabled
```

Restart the worker.

Do not delete provider/order records during an incident.

## PayPal evidence and rollback

Record sandbox buyer approval, authoritative completed capture, a real app's
verified webhook, refund and lost-response reconciliation. Simulator events do
not prove app verification. Keep staging Printful fulfillment disabled.

Record the live merchant/capture, actual gross/fees/net where known, Printful
supplier tax/charges, funding preference and backup source, receipt email,
shipment/tracking and reconciliation. Held receipts are not proof of spendable
balance. A funding decline holds fulfillment for owner review; never charge the
buyer again to retry Printful. Refund and Printful cancellation need separate
explicit authorization. Merchant guest/card eligibility must be checked in the
account and actual hosted flow.

No legacy Square payments are reported. Before cutover, inventory actual
Square orders/links/refunds. New Square checkout creation is retired with HTTP
410; existing Square callbacks and provider-specific reconciliation/refunds
remain for recorded history. Never erase identifiers or revoke credentials as
part of deployment. If an unpaid legacy link exists, review and expire it using
its provider-supported operation before opening new checkout.

Rollback closes new checkout and retains additive migrations, frozen quotes,
provider receipts, request IDs and webhook/reconciliation processing. It does
not reopen Square checkout.
