# Printful as the product admin interface

## Owner intent

Printful is the source of truth for the website product catalog. Additions,
removals, names, prices, sizes/colors, SKUs, and product mockup thumbnails must
appear automatically on Black Metal Buddha. This includes all sizes currently
published in Printful. The current charcoal scenes are the four saved product
thumbnails. The API token stays on the server.

## Design

A read-only scheduled importer fetches the complete paginated saved-product
catalog, validates product/variant identity and prices, and downloads native
mockup thumbnails with a separate unauthenticated HTTP client. A local product
registry and the existing variant table are updated in one transaction. Images
are cached under content-addressed local URLs, keeping the existing image CSP.
The website, product routes, cart metadata, sitemap, and order snapshots read
this registry. Product slugs remain stable when names change.

A successful complete snapshot hides missing or ignored products and disables
missing variants. Historical variant rows and order snapshots are preserved.
Failures retain the previous catalog; an incomplete snapshot never removes
products. A valid empty catalog hides everything. The sync uses a separate
scheduled service, so catalog fetches do not block fulfillment jobs.

Only USD variants with valid positive prices, saved IDs and synced status are
sellable. Product availability follows Printful; independent checkout/payment/
fulfillment approval switches remain closed. Once the approved site launches,
Printful edits can change the catalog without pinning each edit to the original
launch fingerprint. Checkout rejects an excessively stale imported catalog.

Printful's saved-product API does not expose custom design-story descriptions.
Existing approved design stories are retained for the four known designs;
new products receive a concise description using their Printful garment name.

## Failure handling

Validate pagination totals, duplicate IDs/SKUs, product-variant associations,
currency, supported image sources and image decoding before committing.
Download credentials are never sent to image hosts. Restrict image fetches to
Printful CDN hosts and the storefront's static asset paths, following validated
redirects only. Cache immutable filenames and retain old images for historical
links. An API or image error leaves the previous catalog intact.

## Success criteria

- Current four product identities and approved artwork remain unchanged.
- All 28 saved variants and their $35 prices are imported.
- Native Printful images appear across the site under local cached image URLs.
- Added/edited/removed products are reflected on the next completed sync.
- Removed items cannot create new orders; historical orders remain intact.
- Empty and failed snapshots have distinct behavior.
- Purchasing and owner-console gates stay closed during deployment.
- Operational details and credentials stay out of public documentation.

## Responsive storefront

The owner requires layouts to adapt to different displays and resized windows.
Keep the existing desktop/tablet/mobile composition, fluid images and viewport
meta tag. Allow imported names, cards, controls and cart rows to shrink/wrap;
wrap navigation on narrow phones. Product detail controls stack on phones.
