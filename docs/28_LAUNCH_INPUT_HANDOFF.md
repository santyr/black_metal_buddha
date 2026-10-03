# Black Metal Buddha launch handoff

Complete these steps in your accounts and tell me when each is ready. Keep
secret values in the private settings or password manager; send only their
secure location in chat. Deployment-specific records belong in the private
handoff.

## Decisions recorded

- All four physical samples approved; Black Comfort Colors 1717 selected.
- Longchenpa — Rest in Illusion, Meditate on Death and Dharma of Decay approved.
  Lotus of the Void's physical sample is approved and all seven logical SKUs
  were verified correct through the API on 2026-10-03.
- Printful billing confirmed correct by the owner.
- **$35.00 USD per shirt, plus shipping and applicable tax.**
- Shipping will be charged separately using live Printful quotes. The launch
  country list is **the United States and Canada only**.
- SMTP authentication verified on 2026-10-03 after the owner supplied the
  application-specific password. Password spaces are preserved. Delivery
  still needs a check approved by the owner.
- Large sample order total reported by the owner: **$22.10 including shipping**.
  This is not an itemized cost quote for every size or destination.
- All published Printful products and variants should appear on the website,
  currently four designs in S–4XL. Future prices and size changes follow Printful.
- Use the corrected logo and the lighter charcoal scene with faint overlays.

## Step 1 Product approvals recorded

All four physical samples and Printful billing are approved. These approvals
do not need to be supplied again. Lotus already has the correct
`BMB-LOTUS-CC1717-BLK-{SIZE}` SKUs for S–4XL. The API readback confirmed its
existing product and variant IDs, artwork, mockup and $35 prices were preserved;
no recreation was necessary.

For future products, follow [the Printful product admin guide](29_PRINTFUL_PRODUCT_ADMIN.md).
   Save synced variants with positive USD prices and the correct product thumbnail.

**Provide:** Only new product corrections. The API can retrieve saved
product/variant IDs, so you do not need to copy them manually.

For a reusable Dashboard scene, download [the charcoal background](https://blackmetalbuddha.com/static/product-scenes/20261002-charcoal-v2/charcoal-scene-background.jpg),
upload it into Printful's mockup editor, and save the scene. A saved product
thumbnail and a reusable scene preset are separate things. Printful's documented
API can update product preview images but does not expose saved scene editing.
See [Printful's scene instructions](https://help.printful.com/hc/en-us/articles/50266361810577-What-is-the-Custom-Mockup-Maker-and-how-to-use-it).

## Step 2 Prepare staging with the existing Printful store

The owner reports that the current plan allows one Printful store. A second
store is no longer a launch requirement. Staging will use the existing store
for catalog reads and previews, with fulfillment disabled.

1. Create a separate store-scoped private token for the existing store with
   **read-only catalog/product permissions**. Save it privately as the staging
   `PRINTFUL_TOKEN`; use the existing `PRINTFUL_STORE_ID`. Token creation uses
   Printful's Developer Portal; supported work afterward uses the API.
2. Keep staging `PRINTFUL_MODE=disabled` and `PRINTFUL_CONFIRM_ENABLED=false`.
   Do not give staging permission to edit products, place/confirm orders or
   replace production webhook subscriptions.
3. Keep the staging database, service account, settings and Square Sandbox
   credentials separate. Do not copy the production environment file or customer data.
4. Choose a staging hostname and arrange DNS access or the requested DNS record.

**Provide:** Secure location of the read-only token, staging hostname and DNS
contact. There is no need to create another Printful store.

Once read-only access is supplied, I will populate the staging catalog through
the API. Staging payments use Square Sandbox; actual Printful order submission,
production callbacks and fulfillment are checked in the approved controlled
production order in Step 7. Printful draft orders are not a payment sandbox.

## Step 3 Finish payment readiness and staging

Your Square production settings have been supplied. You do not need to submit
them again unless they change.

1. Confirm the merchant account can accept payments and that settlement is set up.
2. Confirm the tax settings you want for launch with the person responsible for them.
3. Obtain separate Square **Sandbox** credentials and location for staging. Save
   them in the private staging settings, keeping production access separate.
4. Leave checkout activation switches closed until the launch checks pass.

**Provide:** Merchant/settlement readiness, approved tax settings, and the secure
location of staging credentials. Production callback delivery and checkout totals
will be checked during the controlled order.

For future credential changes, use the intended application's **Production**
settings. Save `SQUARE_ACCESS_TOKEN`, `SQUARE_LOCATION_ID`,
`SQUARE_WEBHOOK_SIGNATURE_KEY` and the exact `SQUARE_WEBHOOK_NOTIFICATION_URL`
privately, with `SQUARE_ENVIRONMENT=production`. I will verify access and
configuration before using replacement settings.

Reference: [Square access tokens](https://developer.squareup.com/docs/build-basics/access-tokens).

## Step 4 Set up email and support

The production SMTP credentials, sender and support addresses have been supplied.
The sender and support addresses use the Black Metal Buddha domain. Credentials
do not need to be submitted again unless they change.

1. Verify the sender/domain and complete the provider's DNS requirements.
2. Confirm you can receive and reply to mail at the support address.
3. Keep the SMTP password exactly as supplied, including spaces inside its quotes.
4. Approve the prepared delivery check email before it is sent.

**Provide:** Support mailbox confirmation and approval for the delivery check.
Authentication has passed; actual message delivery remains to be verified
before relying on order, tracking and refund messages.

## Step 5 Approve policies and owner access

1. The United States and Canada are approved for launch. Printful's country
   API is a reference list; its store API does not expose an enabled-country
   setting. The website will enforce this approved limit, and shipping service
   must be confirmed by the live quote. See [Printful's country restriction guide](https://help.printful.com/hc/en-us/articles/50262201683089-How-do-I-restrict-certain-countries-from-my-store).
2. Review the website Shipping & Returns, Terms and Privacy pages. Approve them
   or send corrections and the real business/contact details they require.
3. Shipping charged separately using the live Printful quote is approved.
   Supply only changes to this decision.
4. If you want the website owner console activated, explicitly say **Enable the
   owner console**. Credentials alone do not activate it. Product management
   stays in Printful.

**Provide:** Policy approval/edits, changes to the approved countries, and owner-console
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
