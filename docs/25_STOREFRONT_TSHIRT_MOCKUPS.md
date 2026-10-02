# Storefront T-shirt Mockups

## Production policy: use Printful-native mockups

The storefront should represent the actual production product as closely as possible. The selected shirt is **Comfort Colors 1717**, black, fulfilled through Printful. For production storefront images, the source of truth is therefore **Printful's own Mockup Generator**, not a hand-drawn or generic T-shirt silhouette.

Printful documents its mockups as high-quality product images intended for websites, store listings, and social media. Its Mockup Generator API renders the selected catalog product and variant with the submitted artwork. Generated mockup URLs are temporary, so this repository downloads and stores the finished images under `app/static/products/`.

The production mockup refresher is:

```
tools/refresh_printful_mockups.py
.github/workflows/refresh-printful-mockups.yml
```

It currently targets Printful catalog product **586**, Comfort Colors 1717, and by default generates a **Black / Medium / DTG front** representative image for each design. The catalog variant ID is resolved live from Printful instead of being hard-coded.

### Why Medium?

The storefront needs one representative hero image per design. The actual launch catalog remains S–2XL. Medium is used only to select a representative black garment mockup; checkout and fulfillment still use the customer's exact saved Printful variant.

### Artwork source

The refresher sends Printful the approved public production masters from:

```
black_metal_buddhist_prints/03_two_ink_png/
```

CI pins those URLs to the commit being built. The approved masters are transparent 3600 × 4800 PNGs at nominal 300 DPI.

### Lifelike rendering

Printful's documented `lifelike` mockup option is enabled by default. Printful describes it as a mockup-only effect for simulating how artwork appears on dark-color products. It does not alter the production print file.

### Main mockup style

The default requested style is **Flat / Front**. This keeps the primary listing image product-focused and avoids depending on a human model while still using Printful's actual garment rendering, folds, proportions, seams, collar, color, and print simulation.

The workflow accepts different Printful option group/option values if another native style is preferred later.

## Running the native refresher

The GitHub workflow is intentionally manual because Printful's mockup generation is rate-limited and should not run on every source-code push.

Repository Actions secrets:

```
PRINTFUL_TOKEN
PRINTFUL_STORE_ID   # needed for account-level tokens; otherwise optional
```

Then run **refresh native Printful shirt mockups** from GitHub Actions.

The workflow:

1. resolves the current Black / Medium Comfort Colors 1717 catalog variant from Printful;
2. submits each approved front-print master to Printful's Mockup Generator;
3. waits for the asynchronous tasks;
4. downloads the temporary Printful PNGs;
5. composites transparent provider-native garment renders over the BMB Ash Charcoal background;
6. writes consistent 900 × 900 WebP storefront assets;
7. validates all four files;
8. commits the resulting images back to the current branch.

Generated assets:

```
app/static/products/lotus-of-the-void.webp
app/static/products/dharma-of-decay.webp
app/static/products/meditate-on-death.webp
app/static/products/longchenpa-rest-in-illusion.webp
```

## Fallback generator

`tools/build_storefront_mockups.py` remains only as an emergency/manual fallback. Its workflow no longer runs automatically on `main`, because an automatic synthetic rebuild must never overwrite provider-native Printful images.

Fallback workflow:

```
.github/workflows/build-storefront-mockups.yml
```

Use it only when a Printful-native refresh cannot be performed and temporary storefront imagery is required.

## AI-model mockups

Some Printful mockups may use AI-generated human models. Printful currently flags those styles in its product/mockup UI and notes that advertising disclosures can be required in some jurisdictions. For that reason the main storefront image defaults to the product-only **Flat / Front** style. A human-model or lifestyle image can be added later as a secondary image after its source/disclosure status is reviewed.

## Launch checks

Before sales open:

1. configure the actual saved Printful products for all 20 reserved S–2XL SKUs;
2. record real saved product and synced-variant IDs in the production catalog;
3. verify the saved-product artwork/placement against the approved production masters;
4. run the native mockup refresher;
5. visually compare at least one generated mockup with the approved physical sample;
6. keep mockup images separate from print masters—storefront WebPs must never be submitted to Printful for production.

Current Printful references:

- https://developers.printful.com/docs/#tag/Mockup-Generator-API
- https://help.printful.com/hc/en-us/articles/50264186389393-What-are-mockup-images
- https://www.printful.com/custom/mens/t-shirts/unisex-garment-dyed-heavyweight-shirt-comfort-colors-1717?productId=586&productSlug=comfort-colors-1717
- https://help.printful.com/hc/en-us/articles/50264190892433-Do-I-need-to-disclose-that-my-mockups-show-AI-generated-models
