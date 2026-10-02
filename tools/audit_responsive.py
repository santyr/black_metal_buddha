"""Check rendered layout geometry across phones, tablets, and desktops.

Run a local preview server, then:
    PYTHONPATH=. python tools/audit_responsive.py http://127.0.0.1:8088

Requires Playwright and Chromium (``playwright install chromium``), or pass
``--browser /path/to/chromium``. Transactional/admin pages use local template
fixtures; all API requests and form submissions are blocked. No live data,
orders, payments, or launch-gate changes are needed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from playwright.sync_api import sync_playwright
from starlette.requests import Request

from app.catalog import PRODUCTS, PRODUCT_BY_SLUG
from app.main import page_context, templates


WIDTHS = (320, 360, 390, 560, 561, 768, 850, 851, 1000, 1001, 1024,
          1100, 1101, 1180, 1181, 1280, 1440, 1920)
CART = [{"sku": "BMB-LONGCHENPA-CC1717-BLK-XXL",
         "slug": "longchenpa-rest-in-illusion", "name": "Longchenpa — Rest in Illusion",
         "size": "XXL", "color": "Black", "quantity": 2, "priceCents": 3500,
         "currency": "USD"}]


def render(name, **context):
    request = Request({"type": "http", "method": "GET", "path": "/layout-audit"})
    request.state.csp_nonce = "layout-audit"
    return templates.get_template(name).render(page_context(
        request, title="Layout audit", canonical="", phase1_enabled=True, **context))


def fixtures():
    variant = dict(id=1, product_slug=PRODUCTS[0].slug,
                   sku="BMB-LOTUS-CC1717-BLK-XXL", size="XXL", color="Black",
                   retail_price_cents=3500, currency="USD", price_display="$35.00",
                   printful_product_id="123456", printful_variant_id="987654",
                   active=False, sellable=False)
    return {
        "/layout-audit/product": render("product.html", product=PRODUCTS[0], variants=[variant]),
        "/layout-audit/cart": render("cart.html"),
        "/layout-audit/checkout": render("checkout.html"),
        "/layout-audit/catalog": render("admin/catalog.html", products=PRODUCT_BY_SLUG,
                                        variants=[variant], token_new="audit",
                                        token_edit={1: "audit"}, actor="Layout audit"),
    }


# Check internal overflow too: overflow:hidden on a parent can hide a real bug
# without making the document horizontally scroll. Decorative art and explicitly
# scrollable regions are allowed to overflow; visible content and controls aren't.
GEOMETRY = r"""() => {
    const issues = [];
    if (document.documentElement.scrollWidth > innerWidth + 1)
        issues.push('document has horizontal overflow');
    for (const el of document.querySelectorAll('main *')) {
        if (!el.clientWidth || el.closest('[aria-hidden="true"], .admin-table-wrap')) continue;
        if (['auto', 'scroll'].includes(getComputedStyle(el).overflowX)) continue;
        if (el.scrollWidth > el.clientWidth + 1)
            issues.push(`${el.className || el.tagName} overflows its content box`);
        const b = el.getBoundingClientRect();
        if (b.width && (b.left < -1 || b.right > innerWidth + 1))
            issues.push(`${el.className || el.tagName} extends beyond the viewport`);
    }
    // A large heading can split ordinary words while still fitting its box.
    // Check rendered word ranges, rather than assuming no overflow means readable.
    for (const heading of document.querySelectorAll('.page-hero h1, .product-detail-copy h1')) {
        const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            for (const word of node.textContent.matchAll(/\S+/g)) {
                const range = document.createRange();
                range.setStart(node, word.index);
                range.setEnd(node, word.index + word[0].length);
                const lines = new Set([...range.getClientRects()]
                    .filter(rect => rect.width > 0).map(rect => Math.round(rect.top)));
                if (lines.size > 1) issues.push(`heading splits the word "${word[0]}"`);
            }
        }
    }
    const hero = document.querySelector('.hero-copy');
    if (hero) {
        const b = hero.getBoundingClientRect();
        if (Math.abs(b.left + b.width / 2 - innerWidth / 2) > 1)
            issues.push('hero is not centered in the viewport');
        const lead = document.querySelector('.manifesto-lead').getBoundingClientRect();
        const copy = document.querySelector('.manifesto-copy').getBoundingClientRect();
        if (innerWidth <= 850 && (Math.abs(copy.left - lead.left) > 1 || copy.top < lead.bottom))
            issues.push('practice text does not stack below the heading');
    }
    return [...new Set(issues)];
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--browser", help="Use an existing Chromium executable")
    parser.add_argument("--output", default="/tmp/bmb-responsive-audit")
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rendered = fixtures()
    results = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": args.browser} if args.browser else {}))
        context = browser.new_context()
        context.add_init_script("localStorage.setItem('bmb-cart-v2', " + json.dumps(json.dumps(CART)) + ");")
        # The fixtures deliberately use the real templates and scripts, while
        # blocking writes and APIs so this audit cannot reach external providers.
        def route_request(route):
            path = urlsplit(route.request.url).path
            if route.request.method != "GET" or path.startswith("/api/"):
                route.abort()
            elif path in rendered:
                route.fulfill(content_type="text/html", body=rendered[path])
            else:
                route.continue_()
        context.route("**/*", route_request)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        sitemap = context.request.get(base + "/sitemap.xml")
        assert sitemap.status == 200, sitemap.status
        paths = [urlsplit(el.text).path for el in ElementTree.fromstring(sitemap.text()).iter()
                 if el.tag.endswith("}loc")]
        paths.extend(["/cart", "/layout-audit-missing-page", *rendered])
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            for path in paths:
                response = page.goto(base + path, wait_until="load")
                expected = 404 if path == "/layout-audit-missing-page" else 200
                assert response.status == expected, (path, response.status)
                issues = page.evaluate(GEOMETRY)
                if path == "/layout-audit/cart":
                    assert page.locator(".cart-row").count() == 1
                if path == "/layout-audit/checkout":
                    assert page.locator(".checkout-item").count() == 1
                results.append({"path": path, "width": width, "issues": issues})
                if issues:
                    print(f"FAIL: {width}px {path}: {'; '.join(issues)}", flush=True)
                if args.screenshots and width in (390, 768, 1024, 1280, 1920) and path in ("/", "/shop", *rendered):
                    name = path.strip("/").replace("/", "-") or "home"
                    page.screenshot(path=str(output / f"{name}-{width}.png"), full_page=True)
            print(f"Checked {width}px", flush=True)
        browser.close()
    (output / "results.json").write_text(json.dumps(results, indent=2))
    failures = [result for result in results if result["issues"]]
    assert not errors, errors
    assert not failures, f"{len(failures)} failing layouts; see {output / 'results.json'}"
    print(f"PASS: {len(results)} page/viewport layouts; centered hero, stacked practice text, "
          "unclipped cards, populated cart/checkout, and catalog controls.")


if __name__ == "__main__":
    main()
