# Lightning Goats Series

## Awaken the Herd

**Lightning Goats × Black Metal Buddha** collaboration. Design direction approved
October 3, 2026. The garment graphic reads **LIGHTNING GOATS / AWAKEN THE HERD**;
the collaboration is credited in product metadata and copy.

- Garment: black Comfort Colors 1717, matching the existing collection.
- Print: front DTG, 11 × 9.187 inches; blank back and sleeves.
- Colors: bone and ritual red, with black garment negative space.
- Product title: **Awaken the Herd — Lightning Goats × Black Metal Buddha**.
- Series: **Lightning Goats Series**.
- Retail price: **$35.00 USD plus shipping and applicable tax**.
- Sizes: **S, M, L, XL, 2XL, 3XL, 4XL**.
- Product identifier: `BMB-LGAWAKEN`.
- Variant SKUs: `BMB-LGAWAKEN-CC1717-BLK-{SIZE}`.

[Printer instructions](../black_metal_buddhist_prints/LIGHTNING_GOATS_AWAKEN_THE_HERD.txt)
and [print specifications](../black_metal_buddhist_prints/PRINT_SPECIFICATIONS.json)
identify all artwork, exact proofs, source references and placement requirements.

The production SVG is source-derived, not a recovery of missing fine detail.
The AI concept mockup is reference-only; the flat proofs show the actual output.
The owner confirmed physical sample approval on October 3, 2026.
Printful's DTG print-area mapping was
checked for all seven black variants; each uses the same 12 × 16-inch front
area. The native mockup uses proportional 11-inch artwork with a 1-inch top
offset inside that area. Physical sample review covers collar distance,
placement, fine lettering and color reproduction.

## Product creation

Published Printful product: `477756683`, with seven synced variants at $35.00.
The website has imported the product and its charcoal thumbnail. The API
integration below encodes placement in the production canvas.

Create the product in Printful using the cropped `PRINTFUL_FRONT` PNG listed in
the printer instructions. Preserve its aspect ratio and set visible width to
11 inches. Confirm permitted area and placement on each size before saving.
Set the title and series attribution above, choose the retail price, assign
unique SKUs, and generate Printful mockups from that saved product.

## API production file and mockup

The sync-product API's file schema does not expose print-position fields.
For this integration, the approved cropped PNG is placed without scaling on
a transparent 3600 × 4800 production canvas at x=150, y=300 pixels, with its
sRGB profile and 300 ppi metadata preserved. The visible artwork remains
3300 × 2756 pixels, or 11 × 9.187 inches. The canvas encodes the same placement
used in the native Printful mockup instead of auto-enlarging the cropped file.

The production file and 2000 × 2000 thumbnail are in
`app/static/product-scenes/20261003-lightning-goats-r1/`; provenance records
their hashes and the unchanged cropped-art and native-garment pixels.
The thumbnail combines Printful's Flat / Front render with the existing
charcoal scene. It is saved as the Printful product thumbnail so the website
imports the provider-selected image through its normal catalog sync.

The website supplies the approved collaboration copy and series attribution.
Names, prices, sizes, availability and product images continue to follow
Printful. The collaboration appears only after its product is published and
imported there. Product creation and catalog sync do not enable checkout,
approve its physical sample or create an order.
