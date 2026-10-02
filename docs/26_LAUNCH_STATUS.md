# Launch status — 2026-10-02

The public preview is working. Transactional launch is not complete: live
payments, automatic fulfillment, email, and shipment tracking still need real
provider configuration and a controlled production order.

## Confirmed decisions

- Physical sample approved by the owner on 2026-10-01.
- Garment: Comfort Colors 1717 Unisex Garment-Dyed Heavyweight T-Shirt.
- Sizes: S, M, L, XL, XXL (SKU code `2XL`).
- Price: **$35.00 USD per shirt in every size, plus shipping and applicable tax**,
  selected by the owner on 2026-10-02 with Blackcraft as the market reference.
- Four designs and 20 Black variant SKUs. Production and private staging each
  have 20 records priced at 3500 cents, inactive and unsellable. Production’s 20
  Printful mappings are verified; staging mappings remain empty. See [the SKU guide](25_PRODUCT_SKUS.md).
- The corrected approved WebP from remote main commit
  `83bbe7142fd617a1bf4fc6f546c0451d4ec7db51` fully decodes as 384 × 384.
  It is 13,334 bytes, its RIFF length matches the file, and its SHA-256 is
  `6e73625e42533c906a777b18056b98a34e84697983ee181f6f395d4427c4614a`.
  The incomplete PNG was removed upstream. The site uses the repaired WebP
  with cache version `6e73625e`.

## Software and infrastructure evidence

| Requirement | Evidence | Limit |
| --- | --- | --- |
| Source | Remote repository is `santyr/black_metal_buddha`; [PR #20](https://github.com/santyr/black_metal_buddha/pull/20) is merged, and main commit `fd0c4f6` and its 184 verified source files form the base of the reviewed follow-up release | Release metadata records the exact deployed commit and rollback targets |
| Tests | Main passed 129 checks; the follow-up passes 131, including exact logo checksum/container length, all four shirt mockups, and $35 preview price assertions for products, cart, and FAQ | Two dependency deprecation warnings; no live provider transactions |
| Browser | The corrected audit passed all 26 local page/viewport checks against the deployed application, verifying page identity, product images, decoding, preview cart, malformed data, and blocked storage | The post-deployment local browser rerun timed out, as did direct public navigation and optional screenshots; no post-deployment browser pass is claimed. Public HTTPS, asset checksums, and full Pillow decoding pass |
| Printful | Production access is verified; all four products have seven synced Black CC1717 sizes, S–4XL, at $35; the 20 S–XXL production SKUs are mapped; eight signed webhook subscriptions are configured; a synthetic callback passed signature and deduplication checks | Final website size range, native storefront mockups, actual provider event delivery, and real fulfillment/canary remain |
| Database | PostgreSQL 18.6, local peer authentication, migrations through `0007_refund_requests`, 20 reserved production SKUs | No live orders |
| Services | Production web, worker, PostgreSQL, and daily local backup timer verified active | Reconciliation remains disabled until provider credentials are configured |
| Staging | Separate Unix/PostgreSQL role `bmbstaging`, separate database, localhost-only service on 8091 | Public HTTPS, signed callbacks, and sandbox credentials remain |
| Backup | Custom-format backup with checksum restored into a disposable database; migrations and reserved variants verified | Encrypted off-host copy remains |
| Checkout | Public `/checkout` is 404 and `/api/v1/catalog` is 503 | Sales disabled |
| Owner console | `/admin` remains 404 and credentials remain empty | Automatic approval review rejected activation without explicit owner authorization |

The earlier malformed logo in commit `a33277d` is superseded by the repaired
asset above. Earlier evidence about its failed decoding does not describe the
current source. Pricing is settled; actual fulfillment costs must still be
checked in the configured Printful account before sales activation.

## Verification environment

The temporary filesystem quota reached 247 MB of its 300 MB user limit. An
obsolete 116 MB review checkout was removed only after all 175 source files
were verified as preserved in Git and a recovery archive was checked. Usage
fell to 131 MB and normal Chromium blank-page rendering succeeded.

The page audit now waits for document content and verifies the requested URL,
visible heading, branding, and expected product images before checking images
and cart behavior. The previous network-idle wait timed out on otherwise
loadable pages. This follows [Playwright navigation guidance](https://playwright.dev/python/docs/api/class-page#page-goto).

Production Printful access and signing keys are now installed privately. Square
access/signing keys, SMTP sender/access, support contact, and owner-console
credentials remain absent. Staging has separate settings and still lacks provider
access. Live transactions and native storefront mockups remain unverified.

## Remaining owner inputs

Follow [the step-by-step launch handoff](28_LAUNCH_INPUT_HANDOFF.md). It covers:

1. Review the four now-published Printful products and confirm the website size
   range and what the approved physical sample covers.
2. Production Printful access and S–XXL mappings are verified; provide a designated
   test store for isolated staging. Real provider callbacks still need the canary.
3. Provide production and sandbox Square access, merchant location, signed
   webhook configuration, and approved tax settings.
4. Verify an email sender and supply SMTP access plus a working support address.
5. Confirm selling countries and policies; explicitly authorize the owner console
   if it should be enabled.
6. Supply an encrypted off-host backup destination and staging hostname/DNS access.
7. Complete a controlled real checkout, review fulfillment costs, and confirm
   delivered email, tracking, and product quality.

Then record catalog/canary approvals, enable checkout through
[the launch runbook](24_PHASE1_LAUNCH_RUNBOOK.md), and verify public transactions
and monitoring. Do not mark the full store goal complete until that flow is proven.

## Deployment and rollback records

Current and staging point into `/opt/blackmetalbuddha/releases/`. Each release's
`DEPLOYMENT.json` identifies its commit, deployment time, source, and rollback
location. Previous source targets are retained for rollback. Runtime secrets,
local databases, and backup artifacts are excluded from Git.

Prices before the $35 update are archived privately at
`/opt/blackmetalbuddha/backups/pre-price-update-20261002T020525Z/`.
Fresh database dumps and SHA-256 sidecars are under
`/var/backups/blackmetalbuddha/`.
