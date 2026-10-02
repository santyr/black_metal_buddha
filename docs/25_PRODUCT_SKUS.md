# Product SKUs

Created 2026-10-01 after the owner approved the physical sample, selected
Comfort Colors 1717, and confirmed sizes Small through XXL. Checked against remote
`santyr/black_metal_buddha` main commit `a33277dc8e4221ec5068904cfa1ce5c1898cf730`,
which contains all four designs below.

## Convention

`BMB-{DESIGN}-{GARMENT}-{COLOR}-{SIZE}`

Example: `BMB-LOTUS-CC1717-BLK-M` identifies Lotus of the Void on a black
Comfort Colors 1717 in medium.

| Field | Codes |
| --- | --- |
| Brand | `BMB` — Black Metal Buddha |
| Design | `LOTUS`, `DHARMA`, `MEDITATE`, `LONGCHENPA` |
| Garment | `CC1717` — Comfort Colors 1717 |
| Color | `BLK` — Black |
| Size | `S`, `M`, `L`, `XL`, `2XL` (XXL) |

## Product mapping

| Product | Existing design SKU | Medium variant SKU |
| --- | --- | --- |
| Lotus of the Void | `BMB-LOTUS` | `BMB-LOTUS-CC1717-BLK-M` |
| Dharma of Decay | `BMB-DHARMA` | `BMB-DHARMA-CC1717-BLK-M` |
| Meditate on Death | `BMB-MEDITATE` | `BMB-MEDITATE-CC1717-BLK-M` |
| Longchenpa — Rest in Illusion | `BMB-LONGCHENPA` | `BMB-LONGCHENPA-CC1717-BLK-M` |

The existing design SKUs in `app/catalog.py` identify artwork families. The
variant SKUs identify a specific garment, color, and size for inventory,
checkout, and fulfillment. Existing design identifiers stay valid.

## Reservations and launch setup

`../catalog/comfort-colors-1717-skus.csv` reserves 20 distinct SKUs: four designs,
Black, and the five owner-approved sizes from Small through XXL. Black follows
the existing product direction. Current Printful availability must be confirmed
when mapping the variants. Reservations do not make a variant available for purchase.

Every row starts with `active=false` and `sellable=false`. Prices and Printful
IDs are empty because they have not been supplied. The same 20 inactive records
were installed in production PostgreSQL on 2026-10-02. This CSV is a setup
worksheet, not the JSON manifest consumed by `app.manage catalog-import`.

For each selected launch variant:

1. Confirm the size, garment color, artwork, placement, and print technique.
2. Enter its variant SKU in the Printful synced product setup.
3. Record the actual Printful product ID and synced variant ID. The backend uses
   the synced variant ID for fulfillment; the SKU does not replace provider IDs.
4. Set the approved retail price in cents, then mark it active and sellable in
   the BMB catalog. Use only variants actually configured and available.
5. Validate and export the catalog as described in `24_PHASE1_LAUNCH_RUNBOOK.md`.

SKUs are uppercase ASCII, with hyphens separating fields. Keep an issued SKU
stable when its price or provider mapping changes. Give a different garment,
color, or materially different printed product a new SKU; never reuse a retired
SKU for a different item. Use a suffix such as `-R2` if a new artwork edition must
be sold alongside the original.
