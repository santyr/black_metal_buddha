# Storefront T-shirt Mockups

The storefront presents every current product on the same black T-shirt mockup with the Black Metal Buddha **Ash Charcoal** background (`#2B2B2B`).

These images are merchandising previews. They are generated reproducibly from the approved print masters in:

```
black_metal_buddhist_prints/03_two_ink_png/
```

Generated storefront assets:

```
app/static/products/lotus-of-the-void.webp
app/static/products/dharma-of-decay.webp
app/static/products/meditate-on-death.webp
app/static/products/longchenpa-rest-in-illusion.webp
```

## Production placement reference

The production garment is **Comfort Colors 1717**, black, with launch sizes **S through 2XL**. The reserved variant SKUs are documented in `25_PRODUCT_SKUS.md` and `../catalog/comfort-colors-1717-skus.csv`.

Printful guidance checked on 2026-10-01 establishes the reference used by this generator:

- Comfort Colors 1717 supports a **DTG front print**.
- Printful's current T-shirt placement guide describes **12 × 16 inches** as the full-front area for most T-shirts and recommends placing a full-front print approximately **3–4 inches below the collar**.
- Printful's current **15 × 18 inch** large-front list contains Bella + Canvas 3413, Bella + Canvas 3001, and Cotton Heritage MC1082; Comfort Colors 1717 is not listed.
- Product-specific **File guidelines** remain authoritative for the exact production variant and should be rechecked when the Printful saved products are configured.
- Printful recommends PNG at actual print size, the sRGB color profile, and at least 150 DPI for T-shirt artwork. The BMB masters are **3600 × 4800 px at 300 DPI**, corresponding to **12 × 16 inches**, so they do not need to be enlarged for this placement.

The storefront generator therefore models an exact **12:16 (3:4) full-front print box** centered on the chest with its top visually calibrated to Printful's 3–4 inch below-collar guidance.

Unlike the previous mockup implementation, the generator scales the **entire transparent 3600 × 4800 production canvas** rather than cropping to the non-transparent artwork bounds first. This preserves each design's intentional whitespace and offsets recorded in `black_metal_buddhist_prints/PRINT_SPECIFICATIONS.json` and more closely represents how the actual uploaded print file is positioned.

This is a visual merchandising reference, not a substitute for Printful's product-specific template or provider-native mockup.

Current Printful references:

- https://www.printful.com/custom/collections/newapparelvariants/unisex-garment-dyed-heavyweight-shirt-comfort-colors-1717
- https://www.printful.com/ca/blog/t-shirt-design-placement-guide
- https://help.printful.com/hc/en-us/articles/50263171283217-What-should-I-know-about-the-standard-15-18-print-placement-for-DTG-products
- https://help.printful.com/hc/en-us/articles/50264019148177-How-should-I-prepare-my-print-file-for-the-best-results
- https://help.printful.com/hc/en-us/articles/50264024409233-What-is-the-safe-print-area

## Before opening sales

1. Configure the Printful saved products for the exact black Comfort Colors 1717 variants represented by the reserved SKUs.
2. Record the actual Printful product and synced-variant IDs in the production catalog; do not infer them from SKU names.
3. Recheck the File guidelines for every launch size and confirm the DTG front placement and maximum print area before activating a variant.
4. Upload the approved 12 × 16 production master without trimming its transparent canvas, then verify placement in Printful's Design Maker/template.
5. Generate Printful provider-native mockups and compare them with the deterministic storefront previews. Replace or supplement the storefront images if the provider-native result materially differs.
6. Keep the storefront mockups out of the production print-file workflow; only the approved files under `black_metal_buddhist_prints` are print masters.
