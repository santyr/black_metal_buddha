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

## Placement reference

The exact Printful print area depends on the chosen product and variant.

As of this implementation, Printful documents:

- a **15 × 18 inch Large Front** print area on selected DTG products;
- smaller garments can scale a large-front design down to approximately **11.5 × 13.8 inches**;
- important text and design details should remain inside the safe print area;
- product-specific file guidelines/templates remain authoritative.

Because the final production blank is not yet frozen in the main catalog, the storefront generator deliberately uses the conservative **11.5 × 13.8 inch proportion**. The image is centered below the collar and all important artwork is kept well inside the virtual chest print box.

This is a visual placement reference, not a substitute for Printful's product-specific template.

Current Printful references:

- https://support.printful.com/hc/en-us/articles/32700385524252-What-is-the-15-18-large-front-print-area
- https://support.printful.com/hc/en-us/articles/360014068979-What-happens-if-my-design-is-too-large-for-a-garment-size
- https://support.printful.com/hc/en-us/articles/360014007700-What-are-the-requirements-for-my-print-files
- https://developers.printful.com/docs/

## When the production blank is frozen

Before production launch:

1. select the exact Printful blank and variant IDs;
2. query that product's supported placements / print-file dimensions;
3. confirm the exact `front` or `large_front` placement;
4. validate artwork against Printful's product template and safe area;
5. generate provider-native mockups through Printful's Mockup Generator/API;
6. replace or supplement these deterministic storefront mockups if the provider-native output materially differs.

The production print masters remain the files in `black_metal_buddhist_prints`; storefront mockups must never be sent to Printful as print files.
