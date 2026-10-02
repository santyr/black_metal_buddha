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
  have 20 records priced at 3500 cents, inactive and unsellable. Printful mappings
  remain empty. See [the SKU guide](25_PRODUCT_SKUS.md).
- The corrected approved WebP from remote main commit
  `83bbe7142fd617a1bf4fc6f546c0451d4ec7db51` fully decodes as 384 × 384.
  It is 13,334 bytes, its RIFF length matches the file, and its SHA-256 is
  `6e73625e42533c906a777b18056b98a34e84697983ee181f6f395d4427c4614a`.
  The incomplete PNG was removed upstream. The site uses the repaired WebP
  with cache version `6e73625e`.

## Software and infrastructure evidence

| Requirement | Evidence | Limit |
| --- | --- | --- |
| Source | Remote repository is `santyr/black_metal_buddha`; launch work is preserved in draft [PR #20](https://github.com/santyr/black_metal_buddha/pull/20), with corrected main merged into the release source | PR is unmerged; release metadata records the deployed commit |
| Tests | Full release suite passes 128 checks, including exact logo checksum/container length and $35 preview price assertions | Two dependency deprecation warnings; no live provider transactions |
| Browser | Prior local audit passed 26 page/viewport checks, image decoding, preview cart, malformed data, and blocked storage | Public release checks are recorded separately during deployment |
| Printful | Saved-product orders use real `sync_variant_id`, explicit draft creation, gated confirmation, and external-ID lookup; v2 shipping resolves saved IDs to blank catalog IDs; costs/shipments normalized | Real saved products and provider validation remain |
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

## Remaining owner inputs

Follow [the step-by-step launch handoff](28_LAUNCH_INPUT_HANDOFF.md). It covers:

1. Publish the four saved Printful products with the exact SKUs, artwork, blank,
   sizes, technique, and placement. Identify what the approved sample covers.
2. Provide store-scoped Printful API access and actual saved-product mappings.
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
