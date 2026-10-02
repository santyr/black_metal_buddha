# Launch status — 2026-10-02

The public preview is working. Transactional launch is not complete: live
payments, automatic fulfillment, email, and shipment tracking still need real
provider configuration and a controlled production order.

## Confirmed decisions

- The owner approved the physical sample.
- Garment: Black Comfort Colors 1717 Unisex Garment-Dyed Heavyweight T-Shirt.
- Website launch sizes: S, M, L, XL, XXL (`2XL` in SKUs), pending confirmation
  whether to include the saved Printful 3XL and 4XL variants.
- Price: **$35.00 USD per shirt in every size, plus shipping and applicable tax**.
- All four designs are saved in Printful with seven synced sizes each, S–4XL.
  The website's 20 S–XXL variants have verified production mappings and remain
  inactive and unsellable. See [the SKU guide](25_PRODUCT_SKUS.md).
- The corrected approved logo fully decodes and is in use.

## Native mockup scenes

All four products now use Printful Flat / Front renders of the saved Black
Comfort Colors 1717 Medium variant. A shared charcoal texture has faint bone-gray
lotus/thorn and muted-red eclipse overlays around its edges. Lossless scene
assembly preserves every fully opaque native garment pixel. Storefront exports
are 900 × 900 WebPs; saved Printful product thumbnails are 2000 × 2000 JPEGs.
All 28 saved variants, original production files, SKUs, options, and $35 prices
were verified unchanged after the thumbnail updates.

The Lotus render uses the 600 × 800 preview of its existing Printful-uploaded
artwork because the API does not expose its original download URL. Its 3600 ×
4800 production file remains unchanged. The other three use the exact saved
production PNG URLs. These images are visual previews; the physical sample and
canary still establish print and fulfillment quality.

Scene exports and the reusable background live in
`app/static/product-scenes/20261002-charcoal/`. The accompanying `provenance.json`
and `printful-previews.json` record image checksums and provider readback.
This saves product thumbnails, not a reusable Dashboard Scene object. The
background can be uploaded into Printful's scene editor separately.

## Verification and limits

- The earlier application follow-up passed 131 tests and 26 local browser
  checks. This asset update uses image decoding, pixel comparison, checksum
  checks, and provider readback; no new test-suite pass is claimed.
- Production Printful access and signed webhook subscriptions are configured.
  Synthetic signature and deduplication checks passed. Actual provider event
  delivery still needs the real canary.
- Public purchasing and the owner console remain closed. Staging remains
  isolated from production provider credentials.
- Operational deployment, rollback, and backup records are kept privately.
  They are excluded from this public status document.

## Remaining owner inputs

Follow [the step-by-step launch handoff](28_LAUNCH_INPUT_HANDOFF.md):

1. Review the four Printful products and their mockups; confirm the website size
   range and which designs the physical sample approval covers.
2. Provide a designated Printful test store for isolated staging.
3. Provide Square production/sandbox access, merchant location, signed webhook
   configuration, and approved tax settings through a secure channel.
4. Verify the email sender; provide SMTP access and a working support address.
5. Confirm selling countries and policies. Explicitly request owner-console
   activation if desired.
6. Provide an encrypted off-host backup destination and staging hostname/DNS
   access through the secure handoff.
7. Complete a controlled real checkout and confirm fulfillment costs, delivered
   email, tracking, and physical product quality.

After the canary and catalog approvals are recorded, follow
[the launch runbook](24_PHASE1_LAUNCH_RUNBOOK.md) to enable checkout and verify
public transactions and monitoring. The full store goal remains incomplete
until that flow is proven.
