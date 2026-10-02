# Black Metal Buddha Launch Handoff

This document tells you what to do in your accounts and what to provide so I can finish the store. Work through the steps in order. You can hand off each completed step as soon as it is ready.

## Decisions already recorded

- Physical sample approved; garment is Comfort Colors 1717.
- Sizes are S, M, L, XL, and XXL, represented as `2XL` in SKUs.
- All four designs are published in the production Printful store with seven Black sizes each, S–4XL. The website retains the earlier S–XXL launch range pending the owner’s size decision; its 20 reserved SKUs now have verified saved Printful product and variant mappings. See [the SKU worksheet](../catalog/comfort-colors-1717-skus.csv).
- Launch retail price is **$35.00 USD for every size, plus calculated shipping and applicable tax**. No size surcharge is applied.
- The repaired approved logo has passed a complete WebP decode and checksum check. You do not need to provide the logo again.
- Production database, background worker, local backups, restore verification, and private staging are prepared. Public purchasing remains closed while the remaining work is completed.

## Price research and decision

The owner reports that the **Large test T-shirt cost $22.10 USD including shipping**. Record this as the sample order total; the shirt and shipping amounts have not been itemized. Launch retail remains **$35.00 plus separately calculated shipping**.

Checked on 2026-10-02 in the US dollar view. [Printful's 1717 page](https://www.printful.com/custom/mens/all/unisex-garment-dyed-heavyweight-shirt-comfort-colors-1717) displays **$15.60 with one print included**, with US shipping **starting at $4.95**. These are advertised starting figures; size, color, technique, placement, taxes, and delivery address can change the actual cost. They are not a quote for every Black S–2XL variant.

The owner selected **$35 per shirt** on 2026-10-02, using Blackcraft as the market reference. [Blackcraft's Duality tee](https://www.blackcraftcult.com/products/duality-t-shirt) and [What I Like tee](https://www.blackcraftcult.com/products/what-i-like-t-shirt) both list **$35**. What I Like also advertises a multi-buy promotion, so regular list prices are not guaranteed realized selling prices. These are graphic tee references, not confirmation that Blackcraft uses our Comfort Colors blank.

At the advertised $15.60 product cost, $35 leaves **$19.40, or 55.4% of merchandise revenue**, before payment fees, Printful taxes, overhead, claims, and extra print charges. This is a preliminary merchandise margin, not net profit. A starting example customer total is $35 + $4.95 = **$39.95 before tax**, but the site will use the actual shipping quote. I will check real S–2XL costs once your Printful account is available before enabling sales.

Current Printful catalog API prices for Black 1717 variants, checked with the production token on 2026-10-02:

| Size | Catalog product price USD |
| --- | ---: |
| S, M, L, XL | $15.60 |
| 2XL | $17.60 |
| 3XL | $19.60 |
| 4XL | $21.60 |

These are catalog product prices, not delivered-order totals. Shipping, tax, and any order-specific charges must be checked for the actual recipient and saved print setup.

## Step 1 Prepare the Printful store and products

**Production setup completed:** Lotus of the Void, Dharma of Decay, Meditate on Death, and Longchenpa — Rest in Illusion are saved in the Black Metal Buddha store. Each has seven synced Black Comfort Colors 1717 variants at $35.00. Lotus’s generated SKUs were replaced with the reserved BMB SKUs while preserving its saved artwork, variant IDs, and prices. The other three use the approved 3600 × 4800 production PNGs pinned to a verified repository commit. All 20 existing S–XXL website variants are mapped and remain inactive.

**Remaining:** Confirm the website launch range, review the three new saved products in Printful, and confirm which designs the physical sample approval covers. All four native shirt mockups are created and saved as Printful product thumbnails; the real fulfillment canary remains unverified.

**Review the new mockups:**

1. Open Printful → Stores → Black Metal Buddha and review the thumbnails on Lotus of the Void, Dharma of Decay, Meditate on Death, and Longchenpa — Rest in Illusion.
2. Compare the artwork size and placement with your approved physical sample. Tell me which designs that approval covers.
3. Confirm whether the website should retain S–XXL or include the saved Printful 3XL and 4XL variants.
4. For a reusable scene inside Printful’s Dashboard editor, download [the charcoal background](https://blackmetalbuddha.com/static/product-scenes/20261002-charcoal/charcoal-scene-background.jpg), upload it as your background, and save the scene using the available [Custom Mockup Maker controls](https://help.printful.com/hc/en-us/articles/50266361810577-What-is-the-Custom-Mockup-Maker-and-how-to-use-it). The API updates product thumbnails; it does not create a Dashboard Scene preset. Printful may show its newer AI mockup interface instead.

The shirt layers come from Printful’s native Flat / Front renderer. The faint lotus, thorn, and eclipse decorations belong to the shared background. Lotus’s mockup uses the saved uploaded artwork’s provider preview; its full-resolution production print file is preserved. The other three use their saved production PNGs. Mockup images do not replace the physical sample check.

**Reference procedure:**

1. Sign in to [Printful](https://www.printful.com/dashboard). If you already have a store for this project, use it rather than creating a duplicate.
2. For a new custom website store, open **Stores** and choose **Connect via API**. Name it Black Metal Buddha. See [Printful's instructions](https://help.printful.com/hc/en-us/articles/50262225690257-How-do-I-create-and-use-a-manual-order-API-store).
3. Publish one saved product for each design: Lotus of the Void, Dharma of Decay, Meditate on Death, and Longchenpa — Rest in Illusion. Product templates alone are not the saved store products used for fulfillment.
4. Select Comfort Colors 1717, Black, and S/M/L/XL/2XL. Use the approved artwork and the print technique and placement that match your sample. Review any size that is unavailable.
5. Assign each variant its exact SKU from the worksheet, such as `BMB-LOTUS-CC1717-BLK-M`. Keep the artwork attached to those saved variants.
6. Add a billing method and check the account billing details. Confirm your actual product costs, especially 2XL and any additional print placement.
7. Save a screenshot or note of the sampled design, print method, placement, and artwork file revision. Confirm whether the sample approval covers all four designs or identify what still needs review.

**Provide:** Store name or store ID, confirmation that all variants are saved, the approved artwork location, and sample/placement details. You do not need to copy 20 provider IDs by hand: with API access I can retrieve the saved products and match their SKUs.

**I will:** Verify the blank, sizes, artwork, availability, costs, synced product IDs, and synced variant IDs, then fill the catalog mappings. A blank catalog product ID is not the saved printed variant ID.

## Step 2 Provide Printful API access

**Production access completed:** The supplied token was verified for orders, saved-product management, files, and webhooks and stored privately in the production environment file. Eight signed order/shipment event subscriptions are configured at the storefront callback. The public callback rejects invalid signatures and accepts/deduplicates a synthetic signed probe. Actual provider event delivery still needs the real canary. Staging remains isolated and needs a designated test-store configuration.

**Reference procedure:**

1. Open the [Printful Developer Portal](https://developers.printful.com/login) and sign in.
2. Create a private token for this store. Prefer store access limited to Black Metal Buddha.
3. Enable the scopes required for orders, saved product reads, and webhook setup: `orders`, `sync_products`, `file_library`, and `webhooks`. I will verify the token permissions before integration. See [Printful authorization documentation](https://developers.printful.com/docs/#tag/Authorization).
4. Put the token and store ID in the secure server settings as `PRINTFUL_TOKEN` and `PRINTFUL_STORE_ID`, using the secure handoff instructions below.

**Provide:** The secure configuration location and the store ID or store name. If a webhook is already configured, also provide the secure location of its signing keys.

**I will:** Configure and verify signed Printful callbacks at `https://blackmetalbuddha.com/api/v1/webhooks/printful`, store their public/secret keys, and check draft fulfillment before any chargeable confirmation. Use a designated test store for staging; Printful draft testing is not a separate payment sandbox.

## Step 3 Prepare Square payment access

**You do:**

1. Sign in to your Square merchant account. Complete merchant activation and settlement setup, and review your tax configuration with the person responsible for it.
2. Open the [Square Developer Console](https://developer.squareup.com/apps). Create or select the application for Black Metal Buddha.
3. Select **Production**, open **Credentials**, and obtain the production access token. Identify the merchant location that should receive the store's payments. See [Square credential instructions](https://developer.squareup.com/docs/build-basics/access-tokens).
4. Store the token as `SQUARE_ACCESS_TOKEN` and the location ID as `SQUARE_LOCATION_ID` in the production environment file.
5. In **Webhooks**, open **Subscriptions**, add a subscription for `https://blackmetalbuddha.com/api/v1/webhooks/square`, and select `payment.created`, `payment.updated`, `refund.created`, and `refund.updated`. Save its signing key as `SQUARE_WEBHOOK_SIGNATURE_KEY`; the notification URL must exactly match `SQUARE_WEBHOOK_NOTIFICATION_URL`. See [Square production webhook instructions](https://developer.squareup.com/docs/webhooks/movetoprod).
6. Select **Sandbox** and obtain separate sandbox access/location credentials for staging. Keep them in the staging environment file.

**Provide:** Application name, selected merchant location, confirmation of account readiness, and the secure locations of production and sandbox settings. Confirm that Square's tax settings are the settings you want for launch.

**I will:** Verify credentials and signatures, check Square-calculated totals, and run the sandbox payment flow. You do not need to write API code or configure our worker.

## Step 4 Set up transactional email and customer support

**You do:**

1. Choose the email provider you already use or want for order emails. Create or obtain SMTP credentials.
2. Verify the sender address/domain with that provider. Complete any DNS records it requests.
3. Choose the address customers can contact and confirm that you can receive and reply to mail there.
4. Supply `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`, and `SUPPORT_EMAIL` in the secure configuration. The sender and support addresses may be the same if your provider allows it.

**Provide:** Provider name, sender address, support address, confirmation that sender verification is complete, and the secure settings location.

**I will:** Configure email and verify actual delivery of confirmation, tracking, action-required, and refund messages.

## Step 5 Confirm store policies and owner access

**You do:**

1. State whether launch ships only to the US or list the countries you want supported.
2. Review [Shipping and Returns](https://blackmetalbuddha.com/shipping-returns), [Terms](https://blackmetalbuddha.com/terms), and [Privacy](https://blackmetalbuddha.com/privacy). Send any changes, or confirm approval of the published draft policies.
3. Confirm that shipping should be charged separately using Printful's live quote. No flat shipping charge or free-shipping threshold is currently selected.
4. If you want the owner console enabled, reply **Enable the owner console**. Automatic approval review previously rejected exposing `/admin` and creating credentials without explicit authorization. The prepared setup generates credentials and stores them privately on the server.

**Provide:** Countries, policy approval or edits, and owner-console approval. Send any genuine business/contact information needed for the policies; avoid placeholder details.

**I will:** Apply the decisions, check supported destinations, set up the approved owner console, and verify access protection. I will generate the session secret and initial owner password; you do not need to invent those values.

## Step 6 Provide the backup destination and staging hostname

**You do:**

1. Identify an encrypted backup destination outside this VPS, such as storage you already control or a separate backup server. Provide the bucket/container or remote path, region/endpoint if applicable, and secure access location. Include how encryption keys will be retained for restoration.
2. Choose the public staging hostname, for example `staging.blackmetalbuddha.com`, and provide DNS access or arrange the requested DNS record. Private staging already runs on localhost; provider callbacks need a reachable HTTPS endpoint.

**Provide:** Backup destination details and access location, staging hostname, and who can change its DNS.

**I will:** Configure backup transfer, verify retrieval/decryption and a disposable restore, then configure staging HTTPS and signed sandbox callbacks. The existing local backup alone does not satisfy the off-host backup requirement.

## Step 7 Prepare one real test order

**You do:**

1. Choose one configured design and size for the controlled test.
2. Provide the recipient name, email, full shipping address, and optional phone number through the secure handoff.
3. Once I show the exact checkout total, pay the Square checkout link. This is a real purchase and Printful will charge for fulfillment after payment is confirmed.
4. Check the received confirmation email, delivery/tracking messages, and physical shirt. Confirm any defects or unexpected details.

**Provide:** Selected SKU, recipient details, and confirmation of the completed checkout and received messages/product. Approval of chargeable fulfillment will be tied to that concrete test order and total.

**I will:** Verify payment, automatic fulfillment, costs, production, shipment/tracking, reconciliation, and refund behavior. After the canary and catalog approval are recorded, I will enable public checkout and perform the launch smoke checks.

## How to hand off settings securely

Keep production and staging credentials in separate private settings files or password-manager items. Use the private operational handoff for server-specific locations. Update the entries for the relevant step and leave the launch switches at their current values. Tell me which secure file or item is ready; I will validate it and handle activation. Keep secret values out of chat, Git, and this document. Square production and sandbox credentials belong in their separate configurations.

Use this handoff message as you finish each step:

```text
Printful store:
Printful saved products ready:
Artwork and sample details location:
Production Square app and merchant location:
Production credentials secure location:
Staging credentials secure location:
Email provider, sender, and support address:
Selling countries:
Policies approved or edits:
Owner console approval:
Encrypted backup destination and access location:
Staging hostname and DNS contact:
Test SKU and recipient details secure location:
```

You do not need to finish every step at once. Production Printful products and access are now configured. Square production/sandbox access and the verified email sender are the best next handoff; the remaining policy, backup, staging, and canary inputs still apply.
