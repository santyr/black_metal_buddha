# ADR-001 — Lightning Deferred Until Automated USD Settlement Is Available

**Status:** Accepted; amended 2026-10-04 to replace the Square-specific dependency.
**Original date:** 2026-09-17

## Decision

PayPal is the planned payment provider. Lightning remains outside the launch
scope. Do not add LNbits, Strike, Core Lightning, BTCPay or another processor as
part of the PayPal migration. Reopening this ADR requires a separate decision.

## Revisit criteria

An approved provider must offer a documented online Lightning checkout API,
reliable order correlation and server-verifiable payment status, and automatic
USD settlement without manual BTC conversion before Printful fulfillment.

PayPal's documented Pay with Crypto supports Bitcoin-funded payments with USD
settlement, but this does not establish native Lightning invoice or LNURL support.
Do not label that checkout as Lightning or assume arbitrary Lightning wallets work.

Optional Pay with Crypto is a later, separately gated enhancement after merchant
eligibility and actual wallet, settlement and refund behavior are validated.
It is not a launch requirement. See [PayPal integration](03_PAYPAL_INTEGRATION.md).

A possible future Lightning discount remains unapproved for implementation and
must be calculated server-side if later adopted. No Lightning option is shown
until the criteria above and a new acceptance test pass.
