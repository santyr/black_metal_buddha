# Printful Product Admin Implementation Plan

> Implement inline with superpowers:executing-plans. Do not add or run tests unless the owner requests them; use compilation, migration checks, real provider readback and public page/asset verification for this deployment.

**Goal:** Make Printful the automatic source for the full storefront catalog.

**Architecture:** Read-only complete snapshots import into a local registry and
variant table in one transaction. Cache provider mockups locally; a separate
scheduled service refreshes the registry about once a minute. The website and
cart read the latest successful snapshot.

**Tech stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, httpx, Pillow, systemd.

**Spec:** ../../superpowers/specs/2026-10-02-printful-product-admin-design.md

## Global constraints

- Keep credentials server-side and checkout/fulfillment/owner-console gates closed.
- Preserve historical order and variant rows, existing product slugs and print files.
- Preserve the last good catalog on incomplete snapshots or API/image errors.
- Import all published Printful sizes; do not hardcode the old S–XXL range.
- Public documentation excludes server-specific deployment and backup locations.

## Tasks

- [ ] Add persisted product registry/sync state and additive migration.
- [ ] Implement paginated read-only import, validation and safe image cache.
- [ ] Route product lookup, variants, sitemap and public cart metadata through the registry.
- [ ] Replace fixed preview price/size text with imported product information.
- [ ] Add CLI sync/status commands and separate periodic service.
- [ ] Document the Printful UI workflow and API description limitation.
- [ ] Compile changed Python and inspect generated schema/migration code.
- [ ] Review source independently, without adding or running tests.
- [ ] Deploy with backups/rollback; apply migration and configure image storage.
- [ ] Import the real four products/28 variants, enable the timer and verify readback.
- [ ] Verify public product mappings, cached image decoding, sizes, prices and closed gates.
- [ ] Record and publish the source/evidence; update the handoff.
