# Phase 1 — Operations, Reconciliation, and Shipment Tracking

This increment makes the Phase 1 backend recoverable and observable before production checkout is enabled.

## Durable shipments

Printful v2 can emit one `shipment_sent` event for each shipment in a split order and can emit additional shipment events for reshipments.

BMB therefore stores shipments separately from the order.

Each shipment records:

- Printful shipment ID
- status
- tracking number
- tracking URL
- reshipment flag
- shipped time
- delivered time
- returned time

A shipment notification email job is unique to the shipment, not merely the order.

This avoids losing a second tracking number on split orders.

## Order state

Printful's order statuses are mapped deliberately:

| Printful | BMB |
| --- | --- |
| `draft` | fulfillment submitted / draft |
| `inreview` | in production |
| `pending` | in production |
| `inprocess` | in production |
| `onhold` | fulfillment hold |
| `partial` | partially shipped |
| `fulfilled` | shipped |
| `failed` | fulfillment failed |
| `canceled` | canceled |

The first `shipment_sent` event does **not** automatically mean the whole order is shipped.

## Missed shipment webhook repair

Provider reconciliation retrieves:

```
GET /orders/@BMB-...
```

and reads the response's embedded `shipments` list, converting Unix shipment
timestamps to ISO timestamps before upserting tracking records locally.

If the original shipment webhook was missed, this can repair both tracking state and the pending shipment-notification job.

Reference:

- https://developers.printful.com/docs/#tag/Orders-API
- https://developers.printful.com/docs/v2-beta/

## Scheduled reconciliation

Systemd units:

```
deploy/systemd/blackmetalbuddha-reconcile.service
deploy/systemd/blackmetalbuddha-reconcile.timer
```

The timer runs every 15 minutes with a small randomized delay.

**Do not enable the timer yet** unless at least one provider is configured for the environment.

When the Phase 1 sandbox environment is configured:

```bash
sudo cp deploy/systemd/blackmetalbuddha-reconcile.service /etc/systemd/system/
sudo cp deploy/systemd/blackmetalbuddha-reconcile.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now blackmetalbuddha-reconcile.timer
systemctl list-timers blackmetalbuddha-reconcile.timer
```

Manual run:

```bash
python -m app.manage reconcile
```

## Owner attention report

Run:

```bash
python -m app.manage ops-report
```

Machine-readable:

```bash
python -m app.manage ops-report --json
```

Monitoring-friendly:

```bash
python -m app.manage ops-report --json --fail-on-attention
```

Exit code 2 means one or more attention items exist.

The report surfaces:

- failed background jobs
- fulfillment holds/failures
- paid orders older than 30 minutes with no Printful order when fulfillment is expected
- failed refunds
- returned shipments

It intentionally excludes customer email and postal address.

## Tracking on customer order page

The noindex order-status page shows every known shipment independently, including tracking number/link and reshipment status.

The order-status URL remains based on the random BMB order number and never displays email or shipping address.

## Remaining launch gates

This reliability layer does not alter the production blocks.

Still required before production checkout:

- physical sample approval
- final SKU/Printful mappings
- retail pricing
- live Square tax validation
- live shipping quote validation
- Printful confirmation implementation + canary
- transactional email provider configuration
- owner workflow for production refunds
