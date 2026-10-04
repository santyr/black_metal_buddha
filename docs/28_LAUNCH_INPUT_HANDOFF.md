# Black Metal Buddha launch handoff

Complete these steps in your accounts and tell me when each is ready. Keep
secret values in the private settings or password manager; send only their
secure location in chat. Deployment-specific records belong in the private
handoff.

## Decisions recorded

- On 2026-10-04 the owner selected PayPal instead of Square for customer checkout and PayPal for Printful billing. The software migration is implemented on the migration branch; account-specific verification and release remain pending.
- The business is based in **Colorado, USA**. The owner reports Colorado as
  the only jurisdiction for BMB's own tax obligations. No resale certificates
  are held or planned. Do not request certificates or apply a Printful resale
  exemption. The owner-approved checkout uses actual Printful quoted tax/VAT
  separately from merchandise and shipping; no separate Colorado calculator is requested.

- All five published physical samples approved; Black Comfort Colors 1717 selected.
- Longchenpa — Rest in Illusion, Meditate on Death and Dharma of Decay approved.
  Lotus of the Void's physical sample is approved and all seven logical SKUs
  were verified correct through the API on 2026-10-03.
- Printful billing confirmed correct by the owner.
- **$35.00 USD per shirt, plus shipping and applicable tax.**
- Shipping will be charged separately using live Printful quotes. The launch
  country list is **the United States and Canada only**.
- SMTP authentication verified on 2026-10-03 after the owner supplied the
  application-specific password. Password spaces are preserved. The owner
  confirmed the latest website verification email arrived on 2026-10-03.
- Large sample order total reported by the owner: **$22.10 including shipping**.
  This is not an itemized cost quote for every size or destination.
- All published Printful products and variants should appear on the website,
  currently five designs and 35 variants in S–4XL. Future prices and size changes follow Printful.
- Use the corrected logo and the lighter charcoal scene with faint overlays.
- Awaken the Herd is the new Lightning Goats × Black Metal Buddha collaboration,
  published at $35.00 in S–4XL. Its design direction and physical sample are
  approved; the owner confirmed sample approval on 2026-10-03.
  See [the collaboration guide](30_LIGHTNING_GOATS_SERIES.md).

## Step 1 Product approvals recorded

All five published physical samples and Printful billing are approved. These approvals
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
3. Keep the staging database, service account, settings and PayPal Sandbox
   credentials separate. Do not copy the production environment file or customer data.
4. Choose a staging hostname and arrange DNS access or the requested DNS record.

**Provide:** Secure location of the read-only token, staging hostname and DNS
contact. There is no need to create another Printful store.

Once read-only access is supplied, I will populate the staging catalog through
the API. Staging payments use PayPal Sandbox; actual Printful order submission,
production callbacks and fulfillment are checked in the approved controlled
production order in Step 7. Printful draft orders are not a payment sandbox.

## Step 3 Finish payment readiness and staging

PayPal is the approved provider. Previously supplied Square settings are historical;
do not request replacement Square credentials for the new launch.

1. Verify the PayPal Business merchant account and eligibility to accept the intended
   PayPal/card checkout methods. Confirm the merchant account identity.
2. Create separate sandbox and live REST apps, with separate buyer/merchant test
   accounts for sandbox. Store client IDs/secrets privately.
3. After the PayPal listener is deployed, register its exact HTTPS webhook URL
   on each environment's app and record each webhook ID. The implemented settings are
   `PAYPAL_ENVIRONMENT` (`sandbox` or `production`), `PAYPAL_CLIENT_ID`,
   `PAYPAL_CLIENT_SECRET`, `PAYPAL_MERCHANT_ID`, `PAYPAL_WEBHOOK_ID` and
   `PAYPAL_WEBHOOK_NOTIFICATION_URL`. The client/settings are implemented;
   checkout/capture and the verified listener are implemented on the migration branch; app-specific sandbox verification is pending.
4. The checkout tax approach is approved: **$35 per shirt + live shipping +
   Printful's quoted tax separately**. BMB is in Fremont County, Colorado, USA;
   no resale certificates are held or planned. The owner reports accountant
   guidance on filing treatment; that is recorded as supplied professional
   guidance, not an independent legal conclusion. No Colorado GIS key or new
   retail-tax service is requested for this approved approach.
   Configure `CHECKOUT_TAX_MODE=printful_quote` and
   `CHECKOUT_TAX_POLICY_APPROVED=true` in the intended environment only when
   the quote path is ready. Checkout adds the actual `costs.tax + costs.vat`
   from Printful's estimate. A complete explicit zero is valid; missing,
   malformed, pending or unavailable quotes block payment. Supplier fees remain
   supplier costs. Current catalog prices come from the trusted Printful import.
5. Printful PayPal setup is already reported complete. Verify its automatic-payment
   funding preference and backup source during the controlled order; do not assume
   held customer receipts are spendable or ask to repeat completed account setup.
6. Keep checkout/fulfillment activation gates closed until the migration and
   launch checks pass. Optional Pay with Crypto requires separate eligibility,
   approval and testing and is not needed for the initial launch.

**Provide:** Merchant/card readiness and secure locations
of sandbox/live app settings. Do not post secrets. See [PayPal integration](03_PAYPAL_INTEGRATION.md)
and [implementation plan](superpowers/plans/2026-10-04-paypal-migration.md).

## Step 4 Set up email and support

The production SMTP credentials, sender and support addresses have been supplied.
The sender and support addresses use the Black Metal Buddha domain. Credentials
do not need to be submitted again unless they change.

1. Verify the sender/domain and complete the provider's DNS requirements.
2. Receiving the website verification email at the support address is confirmed.
   Confirm you can also reply to support requests if you have not done so.
3. Keep the SMTP password exactly as supplied, including spaces inside its quotes.
4. The approved delivery check is complete. Another verification email does
   not need to be approved or sent for this completed check.

**Provide:** Only remaining support-reply setup or new email corrections.
Authentication and delivery of the website verification email are confirmed.
Order, tracking and refund notifications still need to be checked through the
controlled order in Step 7.

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
4. Pay the approved PayPal checkout. This is a real purchase; Printful
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


## Remaining evidence before release

Software checkout/capture/refund and release gates are implemented on the
migration branch. Provide the private sandbox/live PayPal app settings and
merchant/card readiness, complete policies/staging/support/backup inputs above,
and approve the exact controlled live order costs when presented.

The inspected production database has zero linked Square payment orders and
zero Square/unresolved refunds; no unpaid Square link was found to expire.
Synthetic PostgreSQL restore/migration checks do not establish restoration of
the current production backup. The attempted production export to `/tmp` was
rejected by automatic approval review because it could expose sensitive data.
Before deployment, approve a protected backup/restore destination and restricted
temporary database, or supply evidence from your approved backup procedure.
Live charges/refunds/cancellation and public activation remain separate gates.
