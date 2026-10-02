Black Metal Buddha website and backend audit — 2026-09-20

The verified fixes were deployed to the running storefront. Public HTTPS smoke
checks passed and deployed application file hashes match the workspace.

The approved logo is still awaiting recovery. Its archived WebP contains invalid
image data in the working copy, original Git commit, upstream GitHub copy, and
live response (SHA-256 b36bd362237c6e339b70f5cba97c2f31195346ea4b6538528a4a2645ba25f782).
The former test accepted HTTP 200, a WebP MIME type, and a file length; none proved
that a browser could decode it. A plain SVG text wordmark is now used consistently
in public pages, admin pages, the favicon, and metadata. It is a temporary fallback,
not a reconstruction or replacement of the approved Dzogchen-A artwork. The owner
must supply a valid approved original to restore that artwork.

Verified fixes:

- Replaced references to the broken image with a shared branding URL and valid
  text fallback. Updated the smoke test to inspect image content; added browser
  checks that decode every displayed image.
- Preserved JSON API errors and exception headers. This restores checkout error
  details, Retry-After, Allow, and the WWW-Authenticate admin-login challenge.
- Corrected order-status headings for refunds, returns, canceled fulfillment,
  fulfillment failures, and holds. Added bounded polling for pending payments.
- Prevented late pending/failed refund events from undoing a completed refund and
  causing its amount to be counted twice.
- Prevented late failed-payment events/reconciliation from downgrading an already
  completed payment.
- Canceled queued fulfillment submission for fully refunded orders.
- Prioritized returned-shipment state over the provider's fulfilled order state.
  Shipping notifications are now queued even when reconciliation discovered the
  shipment before the shipment-sent event; the existing job key prevents duplicates.
- Rejected non-finite and out-of-range catalog prices as validation errors rather
  than allowing Decimal conversion exceptions to become server errors.
- Normalized malformed cart entries and tolerated unavailable browser storage.
  Checkout displays server-confirmed subtotals and validation details; blocked
  session storage no longer prevents redirecting to the payment page.
- Fixed long-heading overflow at phone widths. Versioned changed CSS/JavaScript
  URLs so browsers fetch the corrected assets immediately.

Verification:

- 84 pytest tests passed, including API order creation, shipping, authoritative
  pricing/tax totals, checkout reuse, late payment events, refund regressions,
  fulfillment safeguards, authentication headers, and order-status presentation.
- Chromium passed 26 page/viewport checks: all 12 sitemap pages plus cart at
  1280px and 360px, including image decoding and horizontal-overflow checks.
- Browser checks passed for preview-cart add/remove, malformed saved data, and
  unavailable local storage.
- The actual checkout JavaScript passed a mocked browser flow covering shipping
  provider failure and retry, authoritative totals, shipping selection, and
  payment redirect with session storage blocked.
- Python compilation, JavaScript syntax, shell syntax, and git diff whitespace
  checks passed. Existing test-library deprecation warnings remain.
- The public HTTPS storefront smoke test passed after deployment; all deployed
  app files were compared with the reviewed workspace by SHA-256.

Square and Printful flows were tested with mocks. No live orders, charges,
refunds, or fulfillment requests were made. Production sales gates and admin
credentials remain in their existing disabled/unconfigured state. This was a
functional audit of the storefront, backend behavior, and deployment; it does
not establish that every possible concurrency or provider failure is covered.

Rollback copy: /opt/blackmetalbuddha/backups/pre-audit-20260920.tar

Re-run the browser checks using tools/audit_storefront.py and
 tools/audit_checkout.py as documented in README.md. Their local test server
should use a disposable database and disabled production integrations.
