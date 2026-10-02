#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://blackmetalbuddha.com}"
BASE_URL="${BASE_URL%/}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

printf 'Smoke testing %s\n' "$BASE_URL"

health="$(curl -fsS "$BASE_URL/healthz")"
[[ "$health" == "ok" ]] || fail "health endpoint did not return ok"

home="$(curl -fsS "$BASE_URL/")"
grep -q "Black Metal Buddha" <<<"$home" || fail "homepage branding missing"
logo_path="$(sed -n 's/.*<link rel="icon"[^>]*href="\([^"]*\)".*/\1/p' <<<"$home")"
[[ "$logo_path" == /static/brand/* ]] || fail "brand asset missing from homepage"
grep -q 'application/ld+json' <<<"$home" || fail "structured data missing"

headers="$(curl -fsS -D - -o /dev/null "$BASE_URL/" | tr -d '\r')"
grep -qi '^x-content-type-options: nosniff$' <<<"$headers" || fail "nosniff header missing"
grep -qi '^content-security-policy:' <<<"$headers" || fail "Content-Security-Policy missing"

logo_file="$(mktemp)"
trap 'rm -f "$logo_file"' EXIT
logo_headers="$(curl -fsS -D - -o "$logo_file" "$BASE_URL$logo_path" | tr -d '\r')"
grep -qi '^content-type: image/' <<<"$logo_headers" || fail "logo content type is not an image"
python3 - "$logo_file" <<'PY'
import sys
from pathlib import Path
from xml.etree import ElementTree

data = Path(sys.argv[1]).read_bytes()
if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
    assert int.from_bytes(data[4:8], 'little') + 8 == len(data), 'Invalid WebP length'
else:
    assert ElementTree.fromstring(data).tag == '{http://www.w3.org/2000/svg}svg', 'Invalid logo image'
PY

robots="$(curl -fsS "$BASE_URL/robots.txt")"
grep -q 'Sitemap:' <<<"$robots" || fail "robots sitemap declaration missing"

sitemap="$(curl -fsS "$BASE_URL/sitemap.xml")"
grep -q '/products/lotus-of-the-void' <<<"$sitemap" || fail "product missing from sitemap"

product="$(curl -fsS "$BASE_URL/products/lotus-of-the-void")"
grep -q 'Checkout is intentionally disabled' <<<"$product" || fail "Phase 0 checkout guard missing"

printf 'PASS: Phase 0 storefront is healthy.\n'
