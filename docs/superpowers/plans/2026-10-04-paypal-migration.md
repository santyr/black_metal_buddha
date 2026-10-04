# PayPal Migration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkboxes for tracking.

**Goal:** Replace Square with PayPal for new BMB customer payments while keeping automated Printful fulfillment and using PayPal for supplier billing.

**Architecture:** Preserve the FastAPI order service, database-backed jobs and Printful protections. Add PayPal Orders/capture/refund support and verified webhooks; retain Square only for historical reconciliation/refunds during cutover.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, httpx, Jinja2/minimal JavaScript, pytest.

**Spec:** [PayPal integration](../../03_PAYPAL_INTEGRATION.md), approved 2026-10-04.

**Status (2026-10-04):** Tasks 1–4 are implemented and verified. Task 5 software
and release gates are implemented; the reviewed branch passes 310 local checks
and its GitHub checks. Account-specific sandbox/live verification, protected
production backup restoration and the controlled live order remain pending.
Public checkout stays closed. See [current launch status](../../26_LAUNCH_STATUS.md).

**Owner clarification (2026-10-04):** There are no legacy Square payment records.
No historical live-payment migration is required. Preserve the existing schema
and compatibility fixtures while implementing new PayPal sales.

**Tax API finding (2026-10-04):** Printful's
[`POST /orders/estimate-costs`](https://developers.printful.com/docs/#operation/estimateOrderCosts)
includes the tax charged to BMB on fulfillment. The standalone `/tax/rates`
endpoint has been retired. The owner subsequently approved passing through
Printful quoted tax/VAT separately from $35 merchandise and live shipping.
Task 2 implements that approved quote policy and fails closed on incomplete
quotes. The owner reports accountant guidance on filing treatment; it remains
owner-supplied professional guidance, not an independently verified legal finding.

**Owner tax inputs (2026-10-04):** Business based in Colorado, USA; owner reports
Colorado as the only jurisdiction for BMB's own tax obligations. No resale
certificates are held or planned. Do not request a certificate or change Printful
tax exemptions. The supplier's charges may apply to other destinations in its
[state list](https://help.printful.com/hc/en-us/articles/50264701567121-In-which-states-will-I-be-charged-sales-tax).
The approved quote policy uses actual `costs.tax + costs.vat`; a complete
explicit zero is valid. No separate retail-tax service or flat Fremont County
rate is required under the owner-approved approach. Supplier fees remain separate
from customer tax; no tax exemption is applied.

## Global constraints

- USD checkout; approved shipping destinations remain United States and Canada.
- Preserve catalog/prices, product/sample approvals and existing fulfillment gates.
- Server controls totals; completed capture is required before paid state.
- Public checkout and chargeable Printful confirmation remain gated.
- Staging uses the existing Printful store read-only; mock all fulfillment writes.
- PayPal settings/interfaces below are implemented; account credentials are still pending.
- No LNbits, Strike, additional crypto processor or native Lightning integration.
- Pay with Crypto is optional after core checkout; not a public-launch requirement.
- Preserve historical Square identifiers and completed transactions.

## Review focus

- Lost capture response: recover the same capture without charging twice (Tasks 1/3).
- Wrong merchant/order or tampered amount: reject before fulfillment (Task 3).
- Changed address/tax/shipping after approval: require fresh pricing (Task 2).
- Duplicate/reordered refund/reversal events: never re-fulfill or regress state (Task 4).
- Held PayPal proceeds/failed Printful billing: alert and recover without recharging (Task 5).

## Task 1: Provider configuration, durable IDs and PayPal client

**Files:** Create `app/payments/paypal.py`, `tests/test_paypal.py`,
`tests/test_paypal_migration.py`, and the next unused Alembic revision under
`migrations/versions/`. Modify `app/settings.py`, `app/models.py`, `.env.example`.

**Interfaces:** `PayPalClient.create_order(order, *, request_id: str) -> dict`,
`get_order(order_id: str) -> dict`, `capture_order(order_id: str, *, request_id: str) -> dict`,
`get_capture(capture_id: str) -> dict`, `refund_capture(capture_id: str, *, amount_cents: int, currency: str, request_id: str) -> dict`,
`get_refund(refund_id: str) -> dict`, and
`verify_webhook(headers: dict, event: dict) -> bool` (raise a retryable error on outage).

- [x] Write failing tests for sandbox/live host isolation, absent credentials,
  token refresh, request timeout/retry preserving the same request ID, and exact
  cents-to-decimal conversion. Run `pytest -q tests/test_paypal.py` and confirm failures.
- [x] Add `PAYPAL_ENVIRONMENT=sandbox|production`, client ID/secret, merchant ID,
  webhook ID/notification URL; keep credentials server-side. Implement fixed trusted
  PayPal API hosts, bounded timeouts and OAuth token management using httpx.
- [x] Test then add a nullable provider discriminator, unique PayPal order/capture
  and refund identifiers, and persistent operation request IDs. Backfill actual
  legacy Square-linked rows as Square; leave unpaid unbound rows unassigned until
  provider selection. Never rename Square IDs into PayPal fields.
- [x] Verify upgrade against a populated Square fixture preserves its IDs and
  refund history. Run both new test files; require PASS and commit this task.

Task 1 verification: full local suite **195 passed** (2026-10-04); 63 PayPal
client checks cover fixed hosts, OAuth refresh, exact amounts, durable-key retries,
missing-key rejection and verification failures/outages. The populated migration
fixture preserves provider references and rejects a downgrade that would discard
PayPal history. Fresh review findings were covered by failing regression tests
and fixes before the full suite passed. No live provider transactions were made.

## Task 2: Server-priced checkout and tax replacement

**Files:** Modify `app/orders.py`, `app/api_phase1.py`, `app/schemas.py`,
`app/static/checkout.js`, relevant checkout templates under `app/templates/`,
`app/main.py` security policy if payment SDK assets are needed, and `app/settings.py`.
Create `app/tax.py` and `tests/test_paypal_checkout.py`.

**Interfaces:** `calculate_tax_cents(order: Order) -> int` uses the owner-approved
rules/configuration and raises when unavailable; no silent zero-tax fallback.
Planned routes: `POST /api/phase1/orders/{order_number}/paypal-checkout` and
`POST /api/phase1/orders/{order_number}/paypal-capture`. Responses expose a
provider-neutral `checkout_url`; capture uses the stored provider order ID.

- [x] Obtain the owner-approved tax approach before implementing `app/tax.py`.
  Pin US/Canada taxable and legitimately zero-tax fixtures with approved expected
  values; missing configuration must refuse production checkout.
- [x] Write tests for trusted totals, wrong currency, unsupported destination,
  stale catalog, duplicate checkout requests, foreign order access, and changed
  shipping/address after attempt creation. Run the new tests and confirm failures.
- [x] Replace `sync_square_pricing` for new payments with server-owned tax/totals;
  include the exact breakdown and fixed shipping snapshot in the PayPal order.
  Lock the active payment attempt so races cannot create two billable checkouts.
- [x] Replace Square frontend calls/copy with PayPal approval/capture flow, preserve
  order-token ownership, CSRF/rate limits and safe error handling. Record card eligibility as a pending account-specific release check; use PayPal-hosted collection without BMB handling raw card fields.
- [x] Run `pytest -q tests/test_paypal_checkout.py tests/test_backend_inputs.py`
  and the mocked checkout browser audit; require PASS, then commit.

## Task 3: Authoritative capture, verified webhooks and reconciliation

**Files:** Modify `app/api_phase1.py`, `app/orders.py`, `app/reconcile.py`,
`app/jobs.py`, `app/manage.py`. Create `tests/test_paypal_webhooks.py` and
`tests/test_paypal_reconcile.py`.

**Interfaces:** `apply_paypal_capture(session, order, capture: dict) -> bool`
validates identity/payee/order/reference/gross amount/USD and atomically records
payment plus one fulfillment job; returns whether it newly transitioned to paid.
The webhook, synchronous capture and reconciliation paths share this function.

- [x] Write failing tests for approval-only and pending capture (no fulfillment),
  wrong payee/order/currency/amount, invalid signature, verification outage,
  duplicate event/capture, and captured payment whose browser never returns.
- [x] Implement `/api/phase1/webhooks/paypal` verification using the configured
  app webhook ID and PayPal verification endpoint. Accept only verified events;
  persist durable event processing with provider/event uniqueness.
- [x] Handle approved-order notifications with a durable idempotent capture job.
  Validate authoritative capture details and preserve the existing local completed
  payment/paid-order conventions consumed by fulfillment.
- [x] Reconcile lost responses, approved-but-uncaptured orders, pending captures and
  missing jobs; retrieve authoritative provider state before repeating side effects.
- [x] Test concurrent callback/reconciliation and timeout-after-success paths yield
  one payment and one Printful job. Run both new test files plus
  `tests/test_backend_durability.py`; require PASS, then commit.

## Task 4: Refunds, reversals and legacy records

**Files:** Modify `app/refunds.py`, `app/reconcile.py`, `app/admin.py`,
`app/api_phase1.py`, `app/ops.py` and relevant admin templates.
Create `tests/test_paypal_refunds.py`; extend `tests/test_refund_migration.py`.

**Interfaces:** Route refund/reconciliation operations by persisted payment
provider. PayPal refunds reference `paypal_capture_id`; Square records continue
using their existing IDs and client, without becoming selectable for new orders.

- [x] Write failing tests for partial/full refunds, over-refunds, concurrent refunds,
  remote success with lost response, pending/failed refund, dashboard-initiated
  refund, capture reversal and old completion events arriving after refund.
- [x] Add idempotent PayPal capture-refund requests and provider status recovery.
  Preserve payment history, separate Printful cancellation, and flag already-produced
  orders for owner attention on reversal; never trigger fulfillment a second time.
- [x] Verify historical Square refund fixtures still dispatch to Square, and mixed
  provider identifiers cannot refund the wrong transaction.
- [x] Run `pytest -q tests/test_paypal_refunds.py tests/test_refund_migration.py`
  and reconciliation tests; require PASS, then commit.

## Task 5: Readiness gates, funding failures and safe cutover

**Files:** Modify `app/settings.py`, `app/manage.py`, `app/ops.py`,
`deploy/README.md`, deployment smoke checks, `tools/audit_checkout.py`,
`docs/24_PHASE1_LAUNCH_RUNBOOK.md`, `docs/27_PRIVATE_STAGING.md`,
`docs/28_LAUNCH_INPUT_HANDOFF.md`, `docs/26_LAUNCH_STATUS.md`, and `README.md`.
Extend `tests/test_launch_readiness.py`, `tests/test_printful_confirmation.py`
and `tests/test_ops_tracking.py`.

- [x] Write tests that public checkout stays closed without PayPal live readiness,
  approved tax rules and a PayPal-specific live canary. An old Square canary must
  not satisfy the PayPal launch gate.
- [x] Update canary creation/status, production validation and runbooks to PayPal;
  ensure no undocumented settings or Square tax prerequisites remain for new sales.
- [x] Test completed capture plus failed Printful billing: alert/hold, no duplicate
  buyer charge, reconcile external ID before any supplier retry. Preserve cost and
  confirmation checks. Show gross receipts, fees/net where known, supplier charges
  and refunds separately; do not present capture completion as spendable balance.
- [x] Inventory outstanding Square attempts/orders/refunds before cutover. Disable
  new Square checkout creation and expire outstanding unpaid links where supported;
  reconcile late legacy payments safely. Keep legacy webhook/refund access until
  records are settled. Do not automatically revoke credentials or delete history.
- [ ] Run the full `pytest -q` suite and mocked browser audits; require PASS. Verify
  PostgreSQL backup restoration and additive migration before deployment.
- [ ] With public checkout closed, run sandbox buyer approval, capture, real app
  webhook verification, refund and reconciliation checks. Keep Printful writes
  mocked/read-only. Simulator events alone do not satisfy the signature gate.
- [ ] After owner review of exact live costs, run one controlled PayPal order with
  the approved product/recipient. Verify capture, Printful charge via PayPal,
  funding source, order email, production, shipment/tracking and reconciliation.
  Check refund behavior with a suitable controlled transaction; cancellation and
  refunds are separately authorized actions, not implied by payment testing.
- [ ] Record evidence, update completion status and enable public checkout only
  under the existing release approval process. Rollback closes new checkout and
  preserves webhook/reconciliation processing; it does not reopen Square sales.

## Optional follow-up: Pay with Crypto

- [ ] Confirm merchant approval and supported wallets for Pay with Crypto.
- [ ] Follow the dedicated Orders crypto flow, including its automatic-capture
  behavior; verify USD settlement and buyer refund currency with account-specific
  sandbox/live capabilities. Document buyer-facing refund terms.
- [ ] Gate independently and test before advertising Bitcoin payments. Do not call
  it Lightning or make it a dependency of ordinary PayPal/card launch.
