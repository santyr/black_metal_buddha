#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://blackmetalbuddha.com}"
BASE_URL="${BASE_URL%/}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

printf 'Phase 1 smoke testing %s\n' "$BASE_URL"

[[ "$(curl -fsS "$BASE_URL/healthz")" == "ok" ]] || fail "health endpoint failed"

catalog="$(curl -fsS "$BASE_URL/api/v1/catalog")"
python3 - "$catalog" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
if not isinstance(data, list) or not data:
    raise SystemExit("catalog is empty")
for row in data:
    for key in ("sku", "product_slug", "size", "retail_price_cents"):
        if key not in row:
            raise SystemExit(f"catalog row missing {key}")
print(f"Catalog variants: {len(data)}")
PY

checkout_html="$(curl -fsS "$BASE_URL/checkout")"
grep -q 'data-paypal-button' <<<"$checkout_html" || fail "PayPal checkout controls missing"

checkout_status="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/checkout")"
[[ "$checkout_status" == "200" ]] || fail "checkout did not return 200"

admin_status="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/admin")"
[[ "$admin_status" == "401" || "$admin_status" == "404" ]] || fail "admin is exposed without authentication"

robots="$(curl -fsS "$BASE_URL/robots.txt")"
grep -q 'Disallow: /checkout' <<<"$robots" || fail "checkout robots rule missing"
grep -q 'Disallow: /admin' <<<"$robots" || fail "admin robots rule missing"

headers="$(curl -fsSI "$BASE_URL/" | tr -d '\r')"
grep -qi '^content-security-policy:' <<<"$headers" || fail "CSP missing"
grep -qi '^x-content-type-options: nosniff$' <<<"$headers" || fail "nosniff missing"

echo "PASS: Phase 1 public storefront smoke checks passed."
