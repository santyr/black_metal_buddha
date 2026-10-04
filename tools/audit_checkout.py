"""Exercise actual checkout JavaScript with mocked provider/API responses.

Requires playwright, Chromium, and a local development server for static assets.
No orders or payments are created. Run from the repo root with PYTHONPATH=.
"""
import argparse
import json

from playwright.sync_api import sync_playwright
from starlette.requests import Request

from app.main import page_context, templates

parser = argparse.ArgumentParser()
parser.add_argument('base_url')
parser.add_argument('--browser', help='Use an existing Chromium executable; defaults to Playwright Chromium')
args = parser.parse_args()
base = args.base_url.rstrip('/')
request = Request({'type': 'http', 'method': 'GET', 'path': '/checkout'})
request.state.csp_nonce = 'browser-audit'
html = templates.get_template('checkout.html').render(page_context(
    request, title='Checkout audit', canonical=base + '/checkout', phase1_enabled=True))
cart = [{'sku': 'AUDIT-M', 'slug': 'lotus-of-the-void', 'name': 'Lotus of the Void',
         'size': 'M', 'color': 'Black', 'quantity': 2, 'priceCents': 1, 'currency': 'USD'}]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.browser, headless=True)
    context = browser.new_context()
    context.add_init_script('localStorage.setItem("bmb-cart-v2", ' + json.dumps(json.dumps(cart)) + ');')
    # Session storage failure must not prevent redirect to payment.
    context.add_init_script("Object.defineProperty(window, 'sessionStorage', {get() {throw new Error('Storage blocked');}});")
    context.route('**/checkout-audit', lambda route: route.fulfill(content_type='text/html', body=html))
    context.route('**/catalog.json', lambda route: route.fulfill(json={'products': [{
        'slug': 'lotus-of-the-void', 'name': 'Lotus of the Void',
        'image': '/static/products/lotus-of-the-void.webp',
        'variants': [{'sku': 'AUDIT-M', 'variantId': 'AUDIT-VARIANT', 'size': 'M',
                      'color': 'Black', 'priceCents': 3500, 'currency': 'USD', 'available': True}],
    }]}))
    calls = []
    def api_route(route):
        path = '/' + route.request.url.split('/api/', 1)[1].split('/', 1)[1]
        calls.append(path)
        if path != '/orders': assert route.request.headers.get('x-bmb-order-token') == 'audit-owner-token'
        if path == '/orders':
            payload = route.request.post_data_json
            assert payload['items'] == [{'sku': 'AUDIT-M', 'printful_variant_id': 'AUDIT-VARIANT', 'quantity': 2}]
            data = {'order_number': 'BMB-AUDIT', 'order_token': 'audit-owner-token', 'subtotal_cents': 6400, 'currency': 'USD'}
        elif path.endswith('/shipping-rates'):
            if calls.count(path) == 1:
                route.fulfill(status=502, json={'detail': 'Shipping provider temporarily unavailable'})
                return
            data = [{'shipping': 'STANDARD', 'rate_cents': 500, 'currency': 'USD', 'name': 'Standard'}]
        elif path.endswith('/shipping'):
            data = {'shipping_cents': 500}
        elif path.endswith('/paypal-checkout'):
            data = {'checkout_url': 'https://www.sandbox.paypal.com/checkoutnow?token=AUDIT', 'tax_cents': 108, 'total_cents': 7008, 'currency': 'USD'}
        else:
            raise AssertionError(path)
        route.fulfill(json=data)
    context.route('**/api/v1/**', api_route)
    context.route('**/api/phase1/**', api_route)
    context.route('https://www.sandbox.paypal.com/**', lambda route: route.fulfill(body='Mock payment page'))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base + '/checkout-audit')
    page.locator('.checkout-item').wait_for()
    assert page.locator('[data-checkout-subtotal]').inner_text() == '$70.00'
    for name, value in {'name': 'Audit Buyer', 'email': 'audit@example.com', 'address1': '1 Test St',
                        'city': 'Denver', 'state': 'CO', 'postal_code': '80202'}.items():
        page.locator(f'[name="{name}"]').fill(value)
    page.locator('[data-quote-button]').click()
    page.get_by_text('Shipping provider temporarily unavailable', exact=True).wait_for()
    page.locator('[data-quote-button]').click()
    page.locator('[data-shipping-step]').wait_for(state='visible')
    assert page.locator('[data-checkout-subtotal]').inner_text() == '$64.00'
    assert page.locator('[data-checkout-shipping]').inner_text() == '$5.00'
    page.locator('[data-paypal-button]').click()
    page.get_by_text('Pay $70.08 with PayPal', exact=True).wait_for()
    assert page.locator('[data-checkout-tax]').inner_text() == '$1.08'
    assert page.locator('[data-checkout-total]').inner_text() == '$70.08'
    page.locator('[data-paypal-button]').click()
    page.wait_for_url('https://www.sandbox.paypal.com/checkoutnow?token=AUDIT')
    assert not errors, errors
    browser.close()
print('PASS: checkout validation, error display/retry, authoritative totals, shipping, and redirect with blocked session storage.')
