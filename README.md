# Black Metal Buddha

Self-hosted storefront and ecommerce backend for blackmetalbuddha.com.

## Architecture

Black Metal Buddha owns its storefront, catalog, cart, order database, Square integration, and Printful fulfillment orchestration.

- **Square fiat checkout** is the launch payment path.
- **Printful** is the launch fulfillment provider.
- **LNbits and Strike are not dependencies** of this project.
- **Lightning remains deferred** until Square exposes an official online API that can accept Lightning and automatically settle the merchant side to fiat/USD without manual conversion.

## Implementation status

### Phase 0 — storefront

Implemented:

- responsive Black Metal Buddha storefront
- repaired approved Dzogchen-A logo, verified by complete WebP decoding
- four design pages (three core designs and Longchenpa in the Lineage Series)
- SEO metadata, structured data, sitemap, robots rules
- security headers and deployment configuration
- preview mode while transactional launch gates are closed

### Phase 0.5 — physical product validation

**Physical sample approved.** On 2026-10-01 the owner selected Comfort Colors
1717 (Unisex Garment-Dyed Heavyweight T-Shirt) for production.

Public production checkout remains gated on the completed production catalog,
provider configuration, and the live canary. The owner set the launch price
to $35.00 plus shipping on 2026-10-02. The corrected logo from remote commit
`83bbe714` passes checksum, container-length, and full image-decoding checks.

Variant SKU reservations and the naming convention are documented in
`docs/25_PRODUCT_SKUS.md`; the full reservation list is in
`catalog/comfort-colors-1717-skus.csv`.

See docs/16_PHASE0_5_SAMPLE_VALIDATION.md.

### Phase 1 — Square + Printful ecommerce

Software implementation is substantially complete:

- database-backed sellable variants and prices
- customer size/quantity cart
- shipping-address checkout
- live Printful shipping quotes
- Square-hosted checkout
- Square tax synchronization and payment webhooks
- durable orders, jobs, refunds, shipments, and audit logs
- Printful draft + gated production confirmation
- exactly-once / external-ID fulfillment protections
- split-shipment tracking and customer status pages
- transactional email jobs
- provider reconciliation
- owner/admin console
- catalog management and approved-catalog SHA-256 fingerprint
- controlled live production canary
- production launch fail-closed gates
- PostgreSQL backups and restore-verification tooling
- deployment and operational smoke tests

Current deployment (2026-10-02): PostgreSQL and the worker are active, the 20
S–XXL SKU records are installed as inactive, and daily local backups plus a
restore test are verified. Printful saved-product API contract corrections are
deployed. All 20 variants have an owner-selected $35.00 price. Live provider
configuration, saved-product mappings, an off-host backup
destination, owner-console approval, and the controlled live canary remain.

Private staging is installed on `127.0.0.1:8091` with a separate account and
PostgreSQL database. See `docs/27_PRIVATE_STAGING.md` for access and verification.
Provider callbacks and sandbox transactions still require configuration.

**All real-sales gates remain OFF by default.**

See docs/19 through docs/24 for the Phase 1 implementation and launch runbooks.
For the remaining owner inputs, start with [the launch handoff](docs/28_LAUNCH_INPUT_HANDOFF.md).

## Safe defaults

The example configuration deliberately does not permit a real transaction:

~~~
PHASE1_API_ENABLED=false
PRODUCTION_CHECKOUT_ENABLED=false
PHASE0_5_APPROVED=false
PRODUCTION_CATALOG_APPROVED=false
PRODUCTION_CANARY_APPROVED=false
PRODUCTION_CANARY_MODE=false
PRINTFUL_MODE=disabled
PRINTFUL_CONFIRM_ENABLED=false
ADMIN_REFUNDS_ENABLED=false
ADMIN_CANCEL_FULFILLMENT_ENABLED=false
~~~

Do not bypass launch validation. Use the controlled canary and launch runbook.

## Development

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
APP_ENV=development DATABASE_URL=sqlite:///./dev.db alembic upgrade head
APP_ENV=development DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload --port 8088
~~~

Run the test suite:

~~~bash
pytest -q
~~~

Browser checks (requires `pip install playwright` and an installed Chromium):

~~~bash
python tools/audit_storefront.py http://127.0.0.1:8088 --browser /path/to/chromium
PYTHONPATH=. python tools/audit_checkout.py http://127.0.0.1:8088 --browser /path/to/chromium
~~~

The storefront audit decodes images, checks desktop/mobile overflow, and tests
the preview cart. Run it in preview mode. The checkout audit uses mocked API
responses and never creates real orders or payments. Pass `--screenshots` to
the storefront audit to also save homepage screenshots.

## Roadmap

- **Phase 0:** storefront — implemented
- **Phase 0.5:** physical sample approved; Comfort Colors 1717 selected
- **Phase 1:** Square + Printful software — implemented, awaiting physical/canary launch gates
- **Phase 2:** Printful-supported marketplaces/ecommerce channels
- **Phase 3:** SEO/content/marketing expansion
- **Future Lightning:** only when Square provides the required automated Lightning-to-fiat API flow
