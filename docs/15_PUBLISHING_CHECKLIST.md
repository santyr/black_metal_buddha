# Phase 0 Publishing Checklist

This checklist is the gate for publishing the pre-launch catalog at `blackmetalbuddha.com`.

## Repository

- [x] Original Square architecture planning merged (superseded by the 2026-10-04 PayPal plan)
- [x] Phase 0 storefront merged
- [x] Approved Black Metal Buddha logo committed and integrated
- [x] Automated test workflow present
- [ ] Publish-readiness PR merged
- [ ] Exact production commit recorded

- [ ] PayPal migration and new payment/fulfillment canary completed before transactional launch

## Product presentation

- [x] Lotus of the Void page
- [x] Dharma of Decay page
- [x] Meditate on Death page
- [x] Existing mockups clearly used as pre-launch product imagery
- [x] No unapproved prices or sizes shown
- [x] Checkout visibly disabled
- [ ] Physical samples approved before transactional launch

## SEO

- [x] Human-readable page titles and descriptions
- [x] Canonical URLs
- [x] Organization and WebSite structured data
- [x] Product structured data without fabricated Offer/price data
- [x] OpenGraph metadata
- [x] robots.txt
- [x] sitemap.xml
- [x] Cart and 404 pages set to noindex
- [ ] Submit sitemap to Google Search Console after DNS/TLS go live
- [ ] Validate rich-result markup against the public URL

## VPS

- [ ] DNS A record points to VPS
- [ ] AAAA record only if working IPv6 is available
- [ ] Dedicated `blackmetalbuddha` service account exists
- [ ] Repository deployed under `/opt/blackmetalbuddha/current`
- [ ] Virtualenv created and requirements installed
- [ ] `/etc/blackmetalbuddha/blackmetalbuddha.env` installed with production values
- [ ] systemd unit enabled and healthy
- [ ] `curl http://127.0.0.1:8088/healthz` returns `ok`

## Nginx / TLS

- [ ] Existing certificate workflow has a valid certificate for apex and `www`
- [ ] Nginx vhost installed
- [ ] `nginx -t` passes
- [ ] HTTP redirects to HTTPS apex
- [ ] HTTPS `www` redirects to HTTPS apex
- [ ] Approved logo and product images load through Nginx
- [ ] HSTS enabled only after HTTPS behavior is verified

## Public smoke test

Run:

```bash
./deploy/smoke-test.sh https://blackmetalbuddha.com
```

Require a PASS.

Then manually verify:

- [ ] desktop navigation
- [ ] mobile navigation
- [ ] product images
- [ ] product pages
- [ ] preview cart
- [ ] about / FAQ / shipping / privacy
- [ ] branded 404
- [ ] no broken links
- [ ] checkout remains disabled

## After publishing

- [ ] Add property to Google Search Console
- [ ] Submit `/sitemap.xml`
- [ ] Check index coverage after crawl
- [ ] Run Lighthouse or equivalent performance/accessibility audit
- [ ] Watch Nginx and systemd logs for errors
- [ ] Do not begin paid marketing until Phase 1 checkout/fulfillment is proven
