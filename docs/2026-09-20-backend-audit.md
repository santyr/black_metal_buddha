Backend audit and deployment — 2026-09-20

The backend fixes below were deployed after 121 tests passed. The frontend was
separately pulled and deployed from main commit 64b085b, with the previously
working shared-logo reference and cache-versioned assets retained. Backend
changes remain local and uncommitted on top of that commit.

Fixed and verified:

- Workers atomically claim jobs before processing. A second worker cannot claim
  an active job. Claims expire after 15 minutes for crash recovery; unknown job
  types become failed jobs instead of remaining in a perpetual pending loop.
  Failed database transactions are rolled back before recording retry state,
  allowing the rest of a worker batch to continue.
- Refund requests are committed before contacting Square, with a durable UUID
  idempotency key and a reserved/pending state. An uncertain provider response
  can be retried with the identical request after a process restart. Pending
  refunds prevent additional refund requests and pause queued fulfillment.
  The implementation follows Square's documented idempotency-key contract:
  https://developer.squareup.com/reference/square/refunds/refund-payment
- Refund-completion accounting is serialized by order and recomputed from the
  ledger. Concurrent or late events cannot count a completion twice or reverse
  a terminal refund state. REJECTED refunds are handled as terminal failures,
  consistent with Square's PaymentRefund statuses:
  https://developer.squareup.com/reference/square/objects/PaymentRefund
- Signed refund events for refunds initiated outside the application are imported
  when they match a known payment and valid amount/currency. Events that arrive
  while a local request's outcome is unresolved return a retryable response
  rather than guessing a correspondence from the amount alone.
- Reconciliation retries unresolved refund requests with their persisted key.
  Its batches rotate using order update time, so orders outside the first batch
  are eventually examined instead of being permanently starved.
- Admin refund amounts are validated within the error-handling path. An uncertain
  provider response is described as awaiting confirmation, rather than falsely
  claiming the refund failed. Non-finite prices are rejected.
- Malformed authenticated webhook payloads return client errors. Non-ASCII
  signatures/CSRF tokens no longer cause string-comparison exceptions. Duplicate
  event-record insertion races return duplicate acknowledgement when the matching
  event already exists; unrelated database integrity errors still propagate.
- Recipient whitespace, basic email shape, and duplicate cart SKUs are validated
  before provider calls. Duplicate SKU lines cannot bypass the per-variant limit.
- Earlier verified backend fixes remain in place: JSON API errors and authentication
  challenge/retry headers, completed-payment state preservation, full-refund
  fulfillment cancellation, returned-shipment precedence, and deduplicated
  shipping notifications for shipments first discovered by reconciliation.

Verification included real concurrent threads with separate SQLite connections,
restart simulation after an uncertain refund, provider-error recovery, external
refund webhooks, admin responses, malformed payloads, migration preservation and
round-trip checks, and the complete existing suite. All 121 tests passed; two
pre-existing test-library deprecation warnings remain. Python compilation and
Git whitespace checks passed.

Deployment applied migration 0007_refund_requests. The refund table now allows
an unresolved request without a Square ID and stores a unique idempotency key.
The migration retains existing rows and guards downgrades that cannot represent
local requests in the old schema. The deployed model was successfully queried
using the service account after migration. Public HTTPS smoke checks passed.

Rollback code and SQLite backup:
/opt/blackmetalbuddha/backups/pre-backend-durability-20260920/

Important limits: concurrency and migrations were executed against SQLite, not
PostgreSQL. Square and Printful were mocked; no live charge, refund, email, or
fulfillment operation was performed. Sales/fulfillment gates remain disabled.
Job recovery is at least once: a crash after an external acknowledgement can
cause a retry, and SMTP does not provide exactly-once delivery. PostgreSQL and
controlled live-provider validation still belong to the production launch gates.

The initial storefront audit snapshot is in 2026-09-20-site-audit.md. Further
frontend design work is owned by the separate frontend agent.
