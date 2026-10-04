# Architecture

> **Payment decision updated 2026-10-04:** PayPal replaces Square for the planned launch. PayPal migration is not implemented yet. See [PayPal integration](03_PAYPAL_INTEGRATION.md) and [migration plan](superpowers/plans/2026-10-04-paypal-migration.md).


## Core principle

Black Metal Buddha owns the ecommerce state.

PayPal owns payment processing.

Printful owns fulfillment.

LNbits and Strike are not in the production architecture.

## Topology

```text
                       Internet
                          |
                    blackmetalbuddha.com
                          |
                       Nginx/TLS
                          |
                    BMB application
          +---------------+---------------+
          |               |               |
       catalog          orders         admin/ops
          |               |
          |               +-------------------+
          |                                   |
          v                                   v
      PostgreSQL                         PayPal Checkout
                                              |
                                    PayPal-hosted payment
                                              |
                                        PayPal webhook
                                              |
                                              v
                                     verified capture → BMB PAID
                                              |
                                              v
                                           Printful
                                              |
                                       Printful webhook
                                              |
                                              v
                                         BMB status
```

## Recommended stack

- Nginx
- Python + FastAPI
- Jinja2/server-rendered pages
- minimal JavaScript
- PostgreSQL
- systemd
- PayPal Orders v2 API
- Printful API
- database-backed retry jobs

A dedicated queue service is optional at launch.

## Application modules

```text
app/
  main.py
  config.py
  catalog/
  cart/
  orders/
  checkout/
  payments/
    base.py
    paypal.py
  fulfillment/
    printful.py
  webhooks/
    paypal.py
    printful.py
  jobs/
  notifications/
  admin/
  templates/
  static/
```

Do not add an LNbits payment provider module.
Do not add a Lightning provider module until ADR-001 is reopened.

## Order state

Keep payment and fulfillment states separate.

Suggested top-level order states:

```text
CART
PENDING_PAYMENT
PAYMENT_FAILED
PAID
FULFILLMENT_QUEUED
FULFILLMENT_SUBMITTED
FULFILLMENT_HOLD
FULFILLMENT_FAILED
IN_PRODUCTION
PARTIALLY_SHIPPED
SHIPPED
CANCELED
REFUNDED
```

## Provider identifiers

For each order keep:

```text
BMB order number
PayPal order ID
PayPal capture ID
Printful external ID
Printful order ID
```

Example:

```text
BMB-000041
  ↕
PayPal order: ...
  ↕
PayPal capture: ...
  ↕
Printful external_id: BMB-000041
```

## Trust boundaries

### Browser is not authoritative for

- product price
- discount
- shipping
- tax
- total
- payment status
- fulfillment status

### PayPal is authoritative for

- payment completion
- PayPal order/capture identity

### Printful is authoritative for

- fulfillment lifecycle
- shipment/tracking lifecycle

### Local BMB database is authoritative for

- ecommerce order
- product snapshot
- customer shipment request
- correlation of PayPal + Printful records
