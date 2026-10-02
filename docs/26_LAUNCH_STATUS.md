# Launch status — 2026-10-02

The objective remains a working store: browse, select size/quantity, pay through
Square, receive confirmation, automatically fulfill through Printful, and receive
shipment/tracking updates. The public preview is working. Transactional launch
is not complete.

## Confirmed decisions

- Owner approved the physical sample on 2026-10-01.
- Production garment: Comfort Colors 1717, Unisex Garment-Dyed Heavyweight T-Shirt.
- Launch sizes: S, M, L, XL, XXL (SKU size code `2XL`).
- Owner is sourcing the valid approved Dzogchen-A logo; both assets in remote
  commit `a33277d` still fail strict decoding (Chromium accepts the PNG).
- Twenty unique Black variant SKUs have been reserved for the four current
  designs. See `25_PRODUCT_SKUS.md` and `../catalog/comfort-colors-1717-skus.csv`.
  Prices and provider mappings are empty. All 20 records are now installed in
  the production PostgreSQL database, inactive and unsellable.

## Current evidence

| Requirement | Evidence | Status |
| --- | --- | --- |
| Remote product scope | Repository moved to `santyr/black_metal_buddha`; remote `main` is `a33277dc8e4221ec5068904cfa1ce5c1898cf730`; `app/catalog.py` contains Lotus, Dharma, Meditate, and Longchenpa, matching local catalog | Confirmed 2026-10-02 |
| Public preview and HTTPS | `deploy/smoke-test.sh https://blackmetalbuddha.com` passes; public health returns `ok`; HTTP and HTTPS `www` return 301 to HTTPS apex | Verified 2026-10-01 |
| Deployed application | Reviewed Printful correction, worker change, backup unit, and SKU CSV match the workspace by SHA-256 at `/opt/blackmetalbuddha/current`; public smoke check passes after restart | Verified 2026-10-02; source preserved in draft PR #20 |
| Browse and preview cart | Local browser audit passes 26 page/viewport checks at 1280px and 360px, image decoding, add/remove, malformed cart data, and blocked storage | Verified 2026-10-02 |
| Existing software checks | Prior deployed suite: 128 passed; rebased source suite: 129 passed, including upstream PNG signature check, with two dependency deprecation warnings; 7 provider contract failures reproduced before correction, all 8 targeted checks pass afterward | Verified; live providers not covered; signatures do not establish image integrity |
| Remote source checks | GitHub Actions `test` and GitGuardian checks both completed successfully for PR #20 commit `e72ab6eec2d802d18d8901491516a629d44db0c0` | Verified 2026-10-02; PR remains draft and unmerged |
| Printful API contract | v1 saved-product orders use `items.sync_variant_id`, explicit draft creation, gated confirmation, and external-ID lookup; v2 shipping resolves saved IDs to blank catalog IDs; v1 shipments/costs normalized | Reviewed independently and deployed; real provider validation remains |
| Checkout browser behavior | Existing mocked browser audit passes provider failure/retry, server totals, shipping selection, and Square redirect with session storage blocked when run alone | Verified 2026-10-02; no real orders or payments |
| Physical product | Owner approval and garment selection | Approved; sampled design, process, placement, and artwork revision not identified |
| Size/SKU setup | CSV validation and PostgreSQL query: 20 unique SKUs, 0 enabled; each of four products has five sizes; no fabricated prices or Printful IDs | Installed; mapping/pricing outstanding |
| Public checkout | `/checkout` returns 404; `/api/v1/catalog` returns 503 | Disabled |
| Background processing | Web app, worker, PostgreSQL, and daily backup timer report active; ops report exits 0 with no issues | Worker ready; reconciliation installed but disabled until a provider is configured |
| Production database/restore | PostgreSQL 18.6 installed, loopback-only TCP and local peer-authenticated app connection; migrations through `0007_refund_requests`; original SQLite verified empty and backed up | Deployed and verified |
| Backup/restore | Custom-format backup plus SHA-256 restored into `blackmetalbuddha_restore_test`; 20 inactive variants, 0 orders, migration head verified | Local backup/restore verified; off-host copy still required |
| Owner console | Production admin credentials remain empty. Automatic approval review rejected enabling the console without explicit user authorization; approval requested | Disabled pending approval |
| Live payment, fulfillment, email, tracking | No current production canary evidence | Incomplete |
| Approved logo | Remote commit `a33277d` contains files with mismatched documented checksums; WebP fails Pillow and Chromium decoding; PNG fails Pillow decoding but Chromium accepts it; working SVG text fallback remains active | Complete valid original still required |

The initial rebased source test run timed out in a migration subprocess while a
browser audit ran concurrently; rerunning alone passed all 129 tests. Direct
Chromium checks reject the remote WebP and accept the remote PNG; Pillow rejects
both. The PNG's signature check passes despite that integrity failure.

The public browser audit timed out. The successful browser evidence is from the
disposable local server using the installed Playwright headless browser, not a
completed public browser audit. The mocked checkout browser audit initially
timed out while other browser checks were running, then passed when run alone.

## Remaining launch work

1. Set approved retail prices and actual Printful synced product/variant mappings
   for the chosen designs and five sizes. Confirm current stock, print method,
   placement, and final artwork, then validate/export the production catalog.
2. Recover and integrate the valid approved logo and validate image decoding.
3. Configure live Square, signed webhooks, Printful, SMTP, support contact, and
   approved admin access. Redacted production configuration was inspected using
   confirmed passwordless root access: provider, email, support, and admin
   settings are empty. PostgreSQL and physical sample approval are configured;
   checkout/fulfillment gates remain disabled.
4. Configure an encrypted off-host backup destination and enable reconciliation
   after provider credentials are installed. Establish a staging/sandbox provider
   flow. The worker, daily local backup, and disposable restore test are verified.
5. Complete the controlled real transaction,
   confirmation email, Printful production, shipment/tracking, reconciliation,
   and refund checks in `24_PHASE1_LAUNCH_RUNBOOK.md`.
6. Approve the catalog fingerprint and canary, enable public checkout through
   the runbook, then run the public Phase 1 smoke test and monitoring checks.

Do not mark the full goal complete until the production flow is proven. The
reviewed correction and SKU records are deployed. The source snapshot, including
the existing backend and storefront fixes, is preserved in draft PR
[#20](https://github.com/santyr/black_metal_buddha/pull/20), commit
`4fda39bd6615e4daa13732e7488283dff0e199ac`. All 54 changed source files were
read back and checked against the verified review snapshot. The PR targets
`main` and remains unmerged. Local databases and backup artifacts were excluded.

Rollback snapshot:
`/opt/blackmetalbuddha/backups/pre-printful-postgres-20261002T001712Z/`.
It contains the previous environment, modified deployment files, and a consistent
backup of the empty SQLite database. PostgreSQL backup/restore evidence uses
`/var/backups/blackmetalbuddha/blackmetalbuddha-20261002T001938Z.dump` and its
SHA-256 sidecar.

The backup unit initially failed before `ExecStartPre` because its required
`ReadWritePaths` directory did not exist. Allowing that missing path during
namespace setup let the privileged setup command create it; the main backup
command then ran with the intended writable directory. The retry succeeded.
