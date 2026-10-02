# Phase 0.5 — Physical Product & Print Validation

**Status:** Physical sample approved by the owner on 2026-10-01; Comfort Colors 1717 selected as the production garment.
**Purpose:** establish the exact garment, print method, placement, and production artwork that Black Metal Buddha will sell before Phase 1 checkout is enabled.

## Owner decision — 2026-10-01

The owner confirmed that the physical sample is approved and selected the
**Comfort Colors 1717 — Unisex Garment-Dyed Heavyweight T-Shirt**.
The owner supplied a repaired approved WebP logo in remote commit `83bbe714`.
It passed full decoding and checksum validation on 2026-10-02.

The approval does not identify the sampled design, print method, exact placement,
or final artwork revision. Record those details with the Printful product setup.
Launch sizes are Small, Medium, Large, XL, and XXL, as confirmed by the owner.
The owner selected $35.00 per shirt plus shipping on 2026-10-02. Actual Printful
saved-product/variant mappings and fulfillment costs still need validation
before the production catalog can be approved. SKU reservations are in
`25_PRODUCT_SKUS.md` and `../catalog/comfort-colors-1717-skus.csv`.

The sample comparison program below is retained as validation guidance and
history. Comfort Colors 1717 is the selected garment; the other blanks are no
longer competing launch candidates.

## Why this phase is a launch gate

The current artwork is strong enough to define the brand and build the storefront, but the original generated artwork began as lower-resolution design/mockup material before being prepared as larger print files.

No amount of file metadata can substitute for examining the actual garment.

Phase 1 must not publish prices, sizes, Printful variant IDs, or accept customer orders until the production combination has been physically approved.

---

## Original blank candidates

These candidates were checked against Printful's current U.S. catalog on 2026-09-17. Recheck availability, colors, sizes, pricing, and fulfillment regions immediately before creating the products.

| Candidate | Character | Current catalog facts | Role in test |
| --- | --- | --- | --- |
| **Comfort Colors 1717** | garment-dyed, vintage/streetwear character | 100% ring-spun cotton; 6.1 oz/yd² (206.8 g/m²); relaxed fit; pre-shrunk; Black; S–4XL; DTG + DTFlex | **Primary brand-fit candidate** |
| **Cotton Heritage MC1086** | cleaner/heavier premium blank | 100% combed ring-spun cotton; 6.5 oz/yd² (220 g/m²); relaxed fit; side-seamed; Black; S–4XL; DTG + DTFlex | **Primary premium comparison** |
| **Gildan 5000** | conventional, lower-cost classic tee | Black; S–5XL; DTG + DTFlex | fallback / price-sensitive option only |

### Original comparison plan

Begin by comparing **Comfort Colors 1717** and **Cotton Heritage MC1086**.

Do not select the cheaper blank by default. The physical shirt is part of the brand.

The Gildan 5000 remains a fallback if the premium blanks create an unacceptable availability, sizing, or margin problem.

### Source references

- Printful Comfort Colors 1717:
  https://www.printful.com/custom/mens/t-shirts/unisex-garment-dyed-heavyweight-t-shirt-comfort-colors-1717
- Printful Cotton Heritage MC1086:
  https://www.printful.com/custom/mens/t-shirts/mens-premium-heavyweight-tee-cotton-heritage-mc1086
- Printful Gildan 5000:
  https://www.printful.com/custom/mens/t-shirts/unisex-classic-tee-gildan-5000

---

## Print method candidates

### DTFlex

Printful positions DTFlex for sharp edges, fine text, intricate detail, and durable/vibrant reproduction.

That makes it the logical **first** process to test against these designs, because the art contains:

- distressed fine linework
- small lettering
- bone-white detail on a black garment
- muted red accents
- architecture / skeletal line art

Tradeoff: the transfer can have a more noticeable hand and lower breathability than DTG, especially over a large print area.

### DTG

DTG can give a softer, more integrated, vintage-feeling result on cotton, which may suit the Black Metal Buddha aesthetic very well.

Tradeoffs on this artwork:

- fine lines can soften
- tiny distressed gaps can close
- small lettering can lose clarity
- dark-garment white underbase behavior can change the visual result
- semi-transparent distress should not be relied upon

### Production-file rule

For either process:

- use the current highest-quality production files, not the shirt mockup JPGs
- retain transparent negative space rather than a black rectangle
- avoid depending on semi-transparent pixels to create distress on black garments
- inspect minimum line/text sizes at the exact final print dimensions
- use Printful's current process-specific file requirements at order time

Current production art lives under:

```
black_metal_buddhist_prints/01_transparent_png/
black_metal_buddhist_prints/02_two_ink_vector/
black_metal_buddhist_prints/03_two_ink_png/
```

The files in `05_original_mockups/` are reference/mockup images only.

---

# Sequential sample program

## Round A — choose the blank

Use the **same design, same print process, same nominal print dimensions, and same garment size** on both shirts.

Recommended stress-test art:

> **Dharma of Decay**

Why: it combines small headline text, architectural detail, a bone-wheel structure, ravens, candles, fog/texture, and the small “ALL THINGS PASS” line. If this design survives production well, the process is likely capable of the collection's most demanding detail.

Order:

1. Comfort Colors 1717 / Black / **DTFlex** / Dharma of Decay
2. Cotton Heritage MC1086 / Black / **DTFlex** / Dharma of Decay

Use the same wearer size for a direct fit comparison.

### Round A approval criteria

Score both garments from 1–5 for:

| Attribute | Notes |
| --- | --- |
| fabric feel / perceived quality | does it feel like a premium brand product? |
| cut and drape | does it suit the visual identity? |
| collar / construction | does it feel durable and intentional? |
| black garment character | rich black vs garment-dyed/faded character |
| print surface compatibility | does the blank make the art look intentional? |
| comfort | especially under a large front print |
| post-wash fit | shrinkage / distortion |
| likely size-range suitability | check actual Printful availability too |

**Gate:** choose one primary blank.

If neither is acceptable, test another blank before moving forward.

---

## Round B — choose the print process

On the **winning blank**, order:

3. Same size / Black / **DTG** / Dharma of Decay

Compare this directly to the DTFlex version of the same blank from Round A.

### Round B image-quality checklist

Inspect at normal viewing distance and up close:

- “DHARMA OF DECAY” headline
- “ALL THINGS PASS” small text
- narrow wheel/bone elements
- candle details
- raven feather detail
- temple edges
- white coverage over black
- muted red reproduction
- distinction between intentional distress and printing failure
- whether tiny negative-space holes remain open
- edge crispness
- tonal gradients / fog
- print alignment and centering

### Round B wear-quality checklist

Compare:

- hand feel when new
- flexibility when shirt bends
- breathability
- whether the print feels disproportionately heavy
- cracking / edge lifting
- visible change after wash
- whether either process looks too “plastic” or too soft for the intended art

**Gate:** select DTFlex or DTG as the default production process.

A process does not win simply because it is sharper. The physical result must fit the brand.

---

## Round C — collection approval

Once the blank and process are selected, physically approve the entire launch collection.

The stress-test design from Rounds A/B already counts if its selected combination is correct.

Order the remaining designs using the chosen production specification:

4. **Lotus of the Void**
5. **Meditate on Death**
6. **Longchenpa — Rest in Illusion**

Longchenpa is an approved Lineage Series design and must receive the same physical production approval before its variants become sellable.

If Dharma of Decay required artwork changes after Round B, order a corrected final Dharma sample too.

### Each final garment must pass

- artwork is centered
- print dimensions feel intentional on-body
- top of graphic is positioned correctly below collar
- text is readable enough to match the approved art
- no accidental crop
- bone-white looks intentional, not washed out
- red matches collection closely enough
- distress does not become random visual noise
- black garment shows through intended negative space
- no obvious halo/underbase artifacts
- wearer approves fit and comfort
- washed sample remains acceptable

---

# Wash test

Do not approve a combination immediately out of the mailer.

For every candidate used to make the final decision:

1. photograph it before washing
2. wash inside-out using the care instructions we will give customers
3. air dry or use the intended recommended drying method
4. inspect after wash 1
5. repeat to at least wash 3 before final production approval

Record:

- shrinkage
- collar change
- fabric twisting
- print cracking
- transfer lifting
- print fading
- red shift
- loss of fine detail

Keep the winning test shirts as physical production references.

---

# Photography gate

After the production combination is approved:

- photograph the **actual garments**
- replace or supplement AI/reference mockups on the storefront
- capture front full-garment image
- artwork closeup
- collar/fabric closeup
- on-body fit if practical
- consistent lighting across all four designs

Do not remove mockups until real photography is good enough to improve the product presentation.

---

# Data to record after approval

Create a production record for every sellable variant:

```
BMB design slug
BMB SKU
Printful product ID
Printful variant ID
blank manufacturer/model
garment color
garment size
print method
print placement
print width
print height
production art filename
production art checksum
sample approval date
sample notes
```

Only then update the application catalog with actual sellable sizes/prices/Printful mappings.

---

# Phase 0.5 exit criteria

All boxes must be checked before Phase 1 transactional launch:

- [ ] primary blank physically selected
- [ ] print method physically selected
- [ ] exact print dimensions approved
- [ ] all four designs physically approved
- [ ] at least one candidate completed a 3-wash test
- [ ] production art frozen and checksummed
- [ ] Printful product/variant IDs recorded
- [ ] launch size range confirmed
- [ ] actual fulfillment cost captured
- [ ] shipping strategy updated from real Printful data
- [ ] real product photography captured
- [ ] storefront updated with approved physical product facts
- [ ] retail pricing decision made from current costs
- [ ] returns/sizing copy updated for selected blank

After these gates pass, proceed to Square + automated Printful Phase 1.

---

## Current Printful technical references

Recheck these at implementation/order time:

- DTFlex overview:
  https://www.printful.com/dtflex
- DTG file guidance:
  https://help.printful.com/hc/en-us/articles/360014007700-What-are-the-file-requirements-for-DTG-printing
- General file guidelines:
  https://help.printful.com/hc/en-us/articles/360014009840-What-are-Printful-s-recommended-file-sizes-and-resolutions
