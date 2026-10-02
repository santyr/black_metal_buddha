"""Browser smoke audit. Requires playwright and an installed Chromium browser.

Run: python tools/audit_storefront.py http://127.0.0.1:8090
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base_url')
    parser.add_argument('--browser', help='Use an existing Chromium executable; defaults to Playwright Chromium')
    parser.add_argument('--output', default='/tmp/bmb-browser-audit')
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.browser, headless=True)
        context = browser.new_context()
        errors = []
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        sitemap = context.request.get(base + '/sitemap.xml')
        assert sitemap.status == 200
        paths = [urlsplit(el.text).path for el in ElementTree.fromstring(sitemap.text()).iter()
                 if el.tag.endswith('}loc')]
        paths.append('/cart')
        product_paths = [path for path in paths if path.startswith('/products/')]
        results = []
        for width in (1280, 360):
            page.set_viewport_size({'width': width, 'height': 900})
            for path in paths:
                response = page.goto(base + path, wait_until='domcontentloaded')
                assert response.status == 200, (path, response.status)
                assert urlsplit(page.url).path == path, (path, page.url)
                page.locator('h1').wait_for(state='visible')
                assert 'Black Metal Buddha' in page.title(), (path, page.title())
                assert page.locator('img[src*="black-metal-buddha-logo.webp"]').count() > 0, path
                if path == '/shop':
                    assert page.locator('.product-card').count() == len(product_paths), path
                elif path in product_paths:
                    mockup = '/static/products/' + path.rsplit('/', 1)[1] + '.webp'
                    assert page.locator(f'img[src="{mockup}"]').count() > 0, (path, mockup)
                    assert page.locator('[data-add-preview]').count() == 1, path
                images = page.evaluate('''async () => Promise.all([...document.images].map(async img => {
                    try { await img.decode(); return {src: img.getAttribute('src'), valid: img.naturalWidth > 0}; }
                    catch (_) { return {src: img.getAttribute('src'), valid: false}; }
                }))''')
                assert all(img['valid'] for img in images), (path, images)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (path, width, 'horizontal overflow')
                results.append({'path': path, 'width': width, 'images': len(images)})
                print(f'PASS: {width}px {path} ({len(images)} images)', flush=True)
                if path == '/' and args.screenshots:
                    page.screenshot(path=str(output / f'home-{width}.png'), full_page=True)
        page.goto(base + '/products/lotus-of-the-void')
        page.locator('[data-add-preview]').click()
        page.goto(base + '/cart')
        assert page.locator('.cart-row').count() == 1
        page.get_by_role('button', name='Remove').click()
        assert page.locator('.cart-row').count() == 0
        page.evaluate("localStorage.setItem('bmb-preview-cart-v1', '[null,42,{}]')")
        page.reload()
        assert page.locator('.cart-row').count() == 0
        assert not errors, errors
        context.close()
        blocked = browser.new_context()
        blocked.add_init_script("Storage.prototype.getItem = Storage.prototype.setItem = () => { throw new Error('Storage blocked'); };")
        page = blocked.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/products/lotus-of-the-void')
        page.locator('[data-add-preview]').click()
        assert page.locator('[data-cart-count]').inner_text() == '1'
        assert not errors, errors
        browser.close()
        (output / 'results.json').write_text(json.dumps(results, indent=2))
        print(f'PASS: {len(results)} page/viewport checks, decoded images, preview cart, malformed and blocked storage.')


if __name__ == '__main__':
    main()
