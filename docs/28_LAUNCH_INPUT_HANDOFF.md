# Black Metal Buddha launch handoff

Complete these steps in your accounts and tell me when each is ready. Keep
secret values in the private settings or password manager; send only their
secure location in chat. Deployment-specific records belong in the private
handoff.

## Decisions recorded

- Physical sample approved; Black Comfort Colors 1717 selected.
- **$35.00 USD per shirt, plus shipping and applicable tax.**
- Large sample order total reported by the owner: **$22.10 including shipping**.
  This is not an itemized cost quote for every size or destination.
- All published Printful products and variants should appear on the website,
  currently four designs in S–4XL. Future prices and size changes follow Printful.
- Use the corrected logo and the lighter charcoal scene with faint overlays.

## Step 1 Review the products in Printful

1. Open your Black Metal Buddha store in Printful.
2. Review Lotus of the Void, Dharma of Decay, Meditate on Death, and Longchenpa —
   Rest in Illusion. Check garment, artwork, placement, mockup, sizes and prices.
3. Tell me which designs the approved physical sample covers. Identify anything
   that still needs a physical sample or placement review.
4. Check the billing method and actual fulfillment costs, including larger sizes.
5. For future products, follow [the Printful product admin guide](29_PRINTFUL_PRODUCT_ADMIN.md).
   Save synced variants with positive USD prices and the correct product thumbnail.

**Provide:** Approval coverage and any product corrections. The API can retrieve
saved product/variant IDs, so you do not need to copy them manually.

For a reusable Dashboard scene, download [the charcoal background](https://blackmetalbuddha.com/static/product-scenes/20261002-charcoal-v2/charcoal-scene-background.jpg),
upload it into Printful's mockup editor, and save the scene. A saved product
thumbnail and a reusable scene preset are separate things.

## Step 2 Prepare isolated staging access

1. Choose a designated Printful test store for staging. Draft orders in Printful
   are not a separate payment sandbox.
2. Create a store-scoped private API token with the permissions required for
   saved products, files, order operations and webhook setup.
3. Save the token and store ID through the private handoff as `PRINTFUL_TOKEN`
   and `PRINTFUL_STORE_ID`.
4. Choose a staging hostname and arrange DNS access or the requested DNS record.

**Provide:** Test-store name, secure access location, staging hostname and DNS
contact. Production and staging credentials must stay separate.

## Step 3 Finish Square payment setup

1. Open the Square Developer Console and select the intended application.
2. Confirm the merchant account can accept payments and that settlement is set up.
3. Select **Production**. Save its access token and selected merchant location
   as `SQUARE_ACCESS_TOKEN` and `SQUARE_LOCATION_ID` in the private production settings.
4. Set `SQUARE_ENVIRONMENT=production` for those production credentials. Leave
   the checkout activation switches closed until the launch checks pass.
5. Create the payment/refund webhook subscription using the callback shown in
   the private handoff. Save its signing key and exact notification URL as
   `SQUARE_WEBHOOK_SIGNATURE_KEY` and `SQUARE_WEBHOOK_NOTIFICATION_URL`.
6. Confirm the tax settings you want for launch with the person responsible for them.
7. Obtain separate Square **Sandbox** credentials and location for staging.

**Provide:** Confirmation of readiness, approved tax settings, and secure settings
locations. I will validate access and signatures and check checkout totals.
No live charge is needed for credential validation.

Reference: [Square access tokens](https://developer.squareup.com/docs/build-basics/access-tokens).

## Step 4 Set up email and support

1. Choose your email provider and obtain SMTP credentials.
2. Verify the sender/domain and complete the provider's DNS requirements.
3. Choose a support address and confirm you can receive and reply to mail there.
4. Save `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`
   and `SUPPORT_EMAIL` through the private handoff.

**Provide:** Provider, sender and support addresses, verification confirmation,
and secure settings location. I will verify delivery of order, tracking and
refund messages.

## Step 5 Approve policies and owner access

1. State whether launch ships only to the US or list the supported countries.
2. Review the website Shipping & Returns, Terms and Privacy pages. Approve them
   or send corrections and the real business/contact details they require.
3. Confirm shipping is charged separately using the live Printful quote, or
   specify your desired free-shipping threshold or flat shipping policy.
4. If you want the website owner console activated, explicitly say **Enable the
   owner console**. Credentials alone do not activate it. Product management
   stays in Printful.

**Provide:** Countries, policy approval/edits, shipping decision, and owner-console
activation request if wanted. I will apply the approved decisions and verify
access protection.

## Step 6 Provide an off-host backup destination

1. Choose storage outside the website server: a bucket/container or separate
   backup server you control.
2. Supply the destination, region/endpoint where relevant, secure access
   location, and encryption/key-retention requirements through the private handoff.

**Provide:** Destination and secure access location. I will check transfer,
retrieval/decryption and restoration before relying on it.

## Step 7 Complete a controlled real order

1. Choose one design and size for the controlled launch order.
2. Provide the recipient name, email, full address and optional phone privately.
3. Review the exact merchandise, shipping and tax total I show you.
4. Pay the approved Square checkout link. This is a real purchase; Printful
   fulfillment is chargeable after payment is confirmed.
5. Confirm receipt of customer emails, tracking and the physical shirt.
   Report defects or unexpected costs.

**Provide:** Selected product/size, private recipient details, and confirmation
of the received order. I will verify payment, fulfillment, costs, email,
shipment tracking and refund/reconciliation behavior before opening purchasing.

## Handoff message

```text
Step completed:
Account/store/application:
Secure settings location (no secret values):
Decisions or corrections:
Anything still missing:
```

Do not paste tokens, passwords or private recipient information into this public
document, Git, or chat. Leave launch switches unchanged while providing inputs.
