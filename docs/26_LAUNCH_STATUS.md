# Launch status — 2026-10-02

The public preview is available. Purchasing opens after the payment,
fulfillment, customer email and controlled order checks are complete.

## Approved product decisions

- Physical sample approved; Black Comfort Colors 1717 selected.
- Retail price: **$35.00 per shirt, plus shipping and applicable tax**.
- The complete published Printful catalog supplies the website's products,
  names, prices, sizes, colors, SKUs, availability and mockup thumbnails.
- The current four designs each include seven sizes, S–4XL.
- The corrected approved logo is in use.

## Product previews

The four shirt previews use Printful's native Flat / Front renders on the
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

The Chromium job for the source merged into the current release passed in
[GitHub Actions](https://github.com/santyr/black_metal_buddha/actions/runs/37067261103).
It checked 324 page/viewport layouts at 18 widths from 320 to 1920 pixels,
including breakpoint boundaries, heading wrapping, hero centering, tablet
content stacking and populated cart/checkout/admin fixtures. Separate storefront
and mocked checkout audits passed too.

These browser checks use preview data and local fixtures. They do not prove
live payment, fulfillment, email delivery or provider callbacks. The deployed
public catalog was checked separately for its four native mockups, 28 variants,
$35 prices and S–4XL sizes.

## Remaining owner steps

Follow [the launch handoff](28_LAUNCH_INPUT_HANDOFF.md): review the products and
sample coverage; complete payment, email and support setup; approve policies
and selling countries; provide staging and backup inputs; and complete one
controlled real order. Keep credentials and deployment details in the private
handoff, outside public documentation.
