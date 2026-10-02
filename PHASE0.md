# Phase 0 Storefront

Phase 0 makes Black Metal Buddha publishable as a pre-launch catalog while intentionally keeping checkout disabled.

## Status

The pre-launch storefront is deployed and its public HTTPS smoke check passed
on 2026-10-01. The deployed site uses a valid text wordmark. Both logo assets
in remote commit `a33277d` still fail decoding; the approved original is needed.

DNS/TLS and the web service are active. Full store completion requires
the transactional launch procedure in `docs/24_PHASE1_LAUNCH_RUNBOOK.md`.

## Included

- FastAPI + Jinja2 server-rendered storefront
- home, shop, product, about, FAQ, cart, shipping/returns, privacy
- shared Black Metal Buddha wordmark at `/static/brand/black-metal-buddha-wordmark.svg`
- existing shirt mockups served directly from `black_metal_buddhist_prints/05_original_mockups`
- localStorage preview cart (no customer data sent to the server)
- human-readable UI typography with black/bone/red visual system
- responsive layout
- canonical metadata, OpenGraph metadata, Organization/WebSite/Product JSON-LD
- robots.txt and XML sitemap
- branded noindex 404 page
- security headers with CSP nonce
- `/healthz`
- pytest smoke/security tests
- systemd and Nginx deployment configuration
- public deployment smoke-test script
- checkout visibly disabled pending Phase 1

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest httpx
PUBLIC_BASE_URL=http://127.0.0.1:8088 uvicorn app.main:app --reload --port 8088
```

## Test

```bash
pytest
```

## Production deployment

See:

- `deploy/README.md`
- `docs/15_PUBLISHING_CHECKLIST.md`
- `deploy/smoke-test.sh`

## Phase boundary

Do not enable checkout in Phase 0.

Square payment handling, the order database, and automated Printful fulfillment belong to Phase 1. Lightning remains deferred until Square exposes the required automated Lightning-to-fiat API flow.
