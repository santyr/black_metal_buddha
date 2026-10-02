# Manage the website catalog in Printful

Printful is the source for the website's product names, retail prices, sizes,
colors, SKUs, availability and product mockup images. The website checks the
complete store catalog about one minute after each sync finishes. A large
catalog or a temporary provider error can delay an update.

## Add a product

1. Open the Black Metal Buddha store in Printful.
2. Add the garment, upload the production artwork and confirm its placement.
3. Select every size and color you want to offer and finish syncing the variants.
4. Set a positive USD retail price for each variant. The current shirts are $35.00
   plus shipping; future edits in Printful change the website's prices.
5. Set a product mockup thumbnail that shows the correct printed garment.
   Use the current charcoal scene for a consistent collection.
6. Save the product. After the next successful sync, check its card in the
   website shop, then open its product page and check the sizes and price.

Products without a usable mockup or synced variants with positive USD prices
stay hidden. Unsupported currencies cannot be purchased.

## Edit a product

1. Edit its name, mockup, retail prices or synced variants in Printful.
2. Save the changes and allow the next sync to finish.
3. Check the shop and product page. Existing website product URLs stay stable
   when you rename a product. Saved carts refresh against the current catalog.

All published sizes are imported, including the current S–4XL range. If variant
prices differ, product cards show the starting price. Out-of-stock variants
cannot be purchased.

## Remove a product

1. Delete the product from the Printful store, or mark it ignored.
2. After the next successful complete sync, it disappears from the shop,
   featured collection and sitemap. Its old product URL returns not found.
3. Historical orders and their product/price snapshots remain intact.

A provider outage, incomplete response or failed image download retains the
previous catalog. Checkout refuses a catalog older than ten minutes once
purchasing is enabled.

## What still needs separate input

The Printful sync product API does not expose custom design-story descriptions.
The existing four stories remain on the website. Send the story for a new design
if you want custom text; otherwise its page uses the product and garment names.

New Printful mockups are displayed as supplied. The website does not generate
new charcoal scenes automatically; choose or upload the correct scene thumbnail
in Printful when creating a product.

Catalog sync does not open checkout, create payments or submit Printful orders.
Payment, fulfillment and owner-console activation have separate launch gates.

API reference: [Printful developer documentation](https://developers.printful.com/docs/).
