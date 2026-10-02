# Product SKUs

The website imports all products and variants published in Printful. The current
four designs use Black Comfort Colors 1717 in S–4XL: **28 unique variant SKUs**.

## Convention

`BMB-{DESIGN}-{GARMENT}-{COLOR}-{SIZE}`

Example: `BMB-LOTUS-CC1717-BLK-M` identifies Lotus of the Void on a black
Comfort Colors 1717 in Medium.

| Field | Codes |
| --- | --- |
| Brand | `BMB` — Black Metal Buddha |
| Design | `LOTUS`, `DHARMA`, `MEDITATE`, `LONGCHENPA` |
| Garment | `CC1717` — Comfort Colors 1717 |
| Color | `BLK` — Black |
| Size | `S`, `M`, `L`, `XL`, `2XL`, `3XL`, `4XL` |

## Product mapping

| Product | Design identifier | Medium variant SKU |
| --- | --- | --- |
| Lotus of the Void | `BMB-LOTUS` | `BMB-LOTUS-CC1717-BLK-M` |
| Dharma of Decay | `BMB-DHARMA` | `BMB-DHARMA-CC1717-BLK-M` |
| Meditate on Death | `BMB-MEDITATE` | `BMB-MEDITATE-CC1717-BLK-M` |
| Longchenpa — Rest in Illusion | `BMB-LONGCHENPA` | `BMB-LONGCHENPA-CC1717-BLK-M` |

Design identifiers describe artwork families. Variant SKUs describe a specific
garment, color and size. Printful saved product/variant IDs remain the provider
identifiers used for fulfillment; a SKU does not replace them.

## Worksheet and product administration

[The SKU worksheet](../catalog/comfort-colors-1717-skus.csv) lists all 28 current
SKU names and the selected $35.00 USD retail price. It is a reference worksheet,
with provider IDs blank and activation flags closed. It does not control the
live website's catalog or open purchasing.

1. Create or edit the saved printed product in Printful.
2. Select the garment, sizes/colors, approved artwork and print placement.
3. Assign each variant its logical SKU and positive USD retail price.
4. Save synced variants and the correct product mockup thumbnail.
5. Check the website after the next completed automatic sync.

Names, prices, variants, availability and product additions/removals follow
Printful. Use [the product admin guide](29_PRINTFUL_PRODUCT_ADMIN.md); manual
website catalog edits/imports are blocked while automatic sync is enabled.
Checkout activation remains a separate launch decision.

Keep issued SKUs stable when changing price. Give a different garment, color
or materially different printed product a new SKU; do not reuse a retired SKU
for a different item. Use an edition suffix such as `-R2` when two artwork
editions are offered together. Stable provider variant IDs protect cart
selections when SKU labels change.
