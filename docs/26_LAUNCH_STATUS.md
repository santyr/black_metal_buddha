# Launch status — payment update 2026-10-04

The public preview is available. Purchasing opens after the payment,
fulfillment, customer email and controlled order checks are complete.

## Payment migration required

The owner selected PayPal instead of Square for customer checkout and PayPal for Printful billing on 2026-10-04. The existing code is still Square-based. PayPal migration, replacement tax handling, sandbox capture/refund/webhook validation and a new controlled live order are launch blockers. See [the migration plan](superpowers/plans/2026-10-04-paypal-migration.md). Optional Pay with Crypto is not a launch requirement; Lightning remains deferred. Existing product and email approvals below remain recorded.

Implementation has begun with PayPal configuration, an Orders/Payments client,
official webhook verification support, exact money conversion and durable
operation identifiers in an additive migration. This foundation does not switch
checkout providers or enable transactions. Checkout/capture processing, webhook
routes, refund routing and release gates remain to be implemented.

The owner confirmed that no legacy Square payment records exist. Printful's
[order estimation API](https://developers.printful.com/docs/#operation/estimateOrderCosts)
returns supplier costs including tax; its standalone tax-rate endpoint is retired.
The supplier tax and our customer-facing tax treatment must be distinguished,
as explained in [Printful's tax guide](https://www.printful.com/ca/taxes-guide).

The owner confirmed that BMB is based in Colorado, USA, and reports Colorado as
the only jurisdiction for its own tax obligations. No resale certificates are
held or planned; leave Printful's exemption settings unchanged. Exact Colorado
checkout-tax calculation, including shipping/delivery-fee treatment, is still
pending. Printful may charge BMB supplier tax for destinations outside Colorado
as listed in its [state list](https://help.printful.com/hc/en-us/articles/50264701567121-In-which-states-will-I-be-charged-sales-tax).

## Approved product decisions

- All five published designs have approved physical samples; Black Comfort Colors 1717 selected.
- Longchenpa — Rest in Illusion, Meditate on Death and Dharma of Decay approved;
  Lotus of the Void's physical sample is approved and all seven logical SKUs
  were verified correct through the API on 2026-10-03. No recreation was needed.
- Printful billing confirmed correct by the owner.
- Retail price: **$35.00 per shirt, plus shipping and applicable tax**.
- The complete published Printful catalog supplies the website's products,
  names, prices, sizes, colors, SKUs, availability and mockup thumbnails.
- Awaken the Herd — Lightning Goats × Black Metal Buddha is published;
  the owner confirmed its physical sample approval on 2026-10-03.
- The current five designs each include seven sizes, S–4XL: 35 variants.
- The corrected approved logo is in use.

## Product previews

The five shirt previews use Printful's native Flat / Front renders on the
shared charcoal background. The background is slightly lighter for contrast
and includes faint lotus, thorn and muted-red eclipse overlays.

Storefront images are 900 × 900 WebPs. The saved product thumbnails are
2000 × 2000 JPEGs. The scene background can also be uploaded to Printful's
Dashboard mockup editor. These previews support the physical sample review;
they do not replace it.

See [the product admin guide](29_PRINTFUL_PRODUCT_ADMIN.md) for adding, editing
and removing products in Printful. Existing product URLs remain stable when
names change, and historical orders retain their original details.

## Browser verification

The unit and Chromium responsive jobs for the collaboration release passed in
[GitHub Actions](https://github.com/santyr/black_metal_buddha/actions/runs/37152600515).
The long collaboration title exposed mobile admin product-selector overflow;
bounded grid and control widths corrected it without changing the audit.

These browser checks use preview data and local fixtures. They do not prove
live payment, fulfillment, email delivery or provider callbacks. The deployed
public catalog was checked separately for five products, 35 variants, $35 prices
and S–4XL sizes. The new collaboration was read back on the homepage, shop,
product page and sitemap, with its imported charcoal Printful thumbnail.

## Remaining owner steps

The owner confirmed receipt of the website verification email on 2026-10-03.
SMTP authentication and this message's delivery are verified. Order, tracking
and refund notification workflows remain part of the controlled order check.

Follow [the launch handoff](28_LAUNCH_INPUT_HANDOFF.md): complete payment,
notification workflows and support readiness; approve policies and tax settings;
provide staging and backup inputs; and complete one
controlled real order. Keep credentials and deployment details in the private
handoff, outside public documentation.
