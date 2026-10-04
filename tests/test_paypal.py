import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from app.payments.paypal import (
    PayPalClient, PayPalConfigurationError, PayPalAPIError,
    PayPalRetryableError, cents_to_decimal, decimal_to_cents,
)
from app.settings import settings, Settings


def config(**kwargs):
    return replace(settings, paypal_environment='sandbox', paypal_client_id='client',
                   paypal_client_secret='secret', paypal_merchant_id='MERCHANT',
                   paypal_webhook_id='WEBHOOK', **kwargs)


def order(**kwargs):
    values = dict(id='local-id', order_number='BMB-TEST', currency='USD',
                  subtotal_cents=3500, discount_cents=0, shipping_cents=510,
                  tax_cents=289, total_cents=4299, shipping_method='STANDARD',
                  customer_name='Buyer', ship_address1='123 Main St', ship_address2=None,
                  ship_city='Boston', ship_state='MA', ship_postal_code='02108',
                  ship_country='US', items=[SimpleNamespace(name_snapshot='Lotus',
                      sku_snapshot='BMB-LOTUS-L', quantity=1, unit_price_cents=3500,
                      line_total_cents=3500)])
    return SimpleNamespace(**(values | kwargs))


def client(handler, cfg=None, **kwargs):
    return PayPalClient(cfg or config(), httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)


def token():
    return httpx.Response(200, json={'access_token': 'token', 'token_type': 'Bearer', 'expires_in': 300})


@pytest.mark.parametrize('cents,value', [(0,'0.00'), (1,'0.01'), (3500,'35.00'),
    (4299,'42.99'), (9999999999999999,'99999999999999.99')])
def test_money_is_exact(cents, value):
    assert cents_to_decimal(cents) == value
    assert decimal_to_cents(value) == cents


@pytest.mark.parametrize('value', [-1, True, 1.5, '35'])
def test_invalid_cents_rejected(value):
    with pytest.raises(ValueError): cents_to_decimal(value)


@pytest.mark.parametrize('value', ['NaN', '1.001', '-1.00', '1e2', 35.0])
def test_invalid_decimal_rejected(value):
    with pytest.raises(ValueError): decimal_to_cents(value)


@pytest.mark.parametrize('environment,host', [('sandbox','api-m.sandbox.paypal.com'),
    ('production','api-m.paypal.com')])
def test_fixed_hosts_oauth_and_capture(environment, host):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.host == host
        if request.url.path == '/v1/oauth2/token':
            assert request.headers['authorization'].startswith('Basic ')
            assert request.content == b'grant_type=client_credentials'
            return token()
        assert request.headers['authorization'] == 'Bearer token'
        assert request.headers['paypal-request-id'] == 'capture-key'
        return httpx.Response(201, json={'id':'ORDER', 'status':'COMPLETED'})
    cfg = replace(config(), paypal_environment=environment)
    assert client(handler, cfg).capture_order('ORDER', request_id='capture-key')['status'] == 'COMPLETED'
    assert len(requests) == 2
    assert requests[-1].extensions['timeout']['read'] <= 20


@pytest.mark.parametrize('missing', ['paypal_client_id', 'paypal_client_secret', 'paypal_merchant_id'])
def test_missing_credentials_fail_before_network(missing):
    with pytest.raises(PayPalConfigurationError):
        client(lambda r: pytest.fail('network called'), replace(config(), **{missing:None})).get_order('ORDER')


def test_environment_and_secret_repr(monkeypatch):
    monkeypatch.setenv('PAYPAL_ENVIRONMENT', 'production')
    monkeypatch.setenv('PAYPAL_CLIENT_SECRET', 'private-paypal-secret')
    cfg = Settings.from_env()
    assert cfg.paypal_api_base == 'https://api-m.paypal.com'
    assert 'private-paypal-secret' not in repr(cfg)
    with pytest.raises(ValueError): replace(cfg, paypal_environment='other').validate_safety()


def test_token_cache_expiry_and_unauthorized_refresh():
    counts = {'tokens':0, 'calls':0}
    now = [0.0]
    def handler(request):
        if request.url.path == '/v1/oauth2/token':
            counts['tokens'] += 1
            return httpx.Response(200, json={'access_token':str(counts['tokens']),
                                           'token_type':'Bearer', 'expires_in':100})
        counts['calls'] += 1
        if counts['calls'] == 4: return httpx.Response(401, json={})
        return httpx.Response(200, json={'id':'ORDER'})
    api = client(handler, clock=lambda:now[0])
    api.get_order('ORDER'); api.get_order('ORDER')
    assert counts['tokens'] == 1
    now[0] = 101
    api.get_order('ORDER'); api.get_order('ORDER')
    assert counts == {'tokens':3, 'calls':5}


@pytest.mark.parametrize('failure', ['timeout', 'server', 'rate'])
def test_write_retries_same_request_and_body(failure):
    writes = []
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        writes.append(request)
        if len(writes) == 1:
            if failure == 'timeout': raise httpx.ReadTimeout('lost capture', request=request)
            return httpx.Response(503 if failure == 'server' else 429, json={})
        return httpx.Response(201, json={'id':'CAPTURE'})
    api = client(handler, sleeper=lambda _:None)
    api.capture_order('ORDER', request_id='durable-capture-key')
    assert len(writes) == 2
    assert writes[0].content == writes[1].content
    assert {r.headers['paypal-request-id'] for r in writes} == {'durable-capture-key'}


def test_exhausted_outage_is_retryable_and_redacted():
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        return httpx.Response(503, json={'message':'secret buyer data'})
    with pytest.raises(PayPalRetryableError) as exc:
        client(handler, sleeper=lambda _:None).capture_order('ORDER', request_id='same-key')
    assert 'secret buyer data' not in str(exc.value)


def test_definitive_failure_does_not_retry():
    writes = []
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        writes.append(request)
        return httpx.Response(422, json={'message':'private information'})
    with pytest.raises(PayPalAPIError) as exc:
        client(handler).capture_order('ORDER', request_id='key')
    assert exc.value.status_code == 422
    assert len(writes) == 1
    assert 'private information' not in str(exc.value)


def test_create_order_has_exact_breakdown_merchant_and_fixed_shipping():
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        payload = json.loads(request.content)
        assert payload['intent'] == 'CAPTURE'
        assert len(payload['purchase_units']) == 1
        unit = payload['purchase_units'][0]
        assert unit['reference_id'] == 'BMB-TEST'
        assert unit['custom_id'] == 'local-id'
        assert unit['payee'] == {'merchant_id':'MERCHANT'}
        assert unit['amount'] == {'currency_code':'USD', 'value':'42.99', 'breakdown':{
            'item_total':{'currency_code':'USD','value':'35.00'},
            'shipping':{'currency_code':'USD','value':'5.10'},
            'tax_total':{'currency_code':'USD','value':'2.89'},
            'discount':{'currency_code':'USD','value':'0.00'}}}
        assert unit['shipping']['address']['country_code'] == 'US'
        assert payload['payment_source']['paypal']['experience_context']['shipping_preference'] == 'SET_PROVIDED_ADDRESS'
        return httpx.Response(201, json={'id':'ORDER'})
    assert client(handler).create_order(order(), request_id='create-key')['id'] == 'ORDER'


@pytest.mark.parametrize('changes', [{'currency':'CAD'}, {'ship_country':'GB'},
    {'total_cents':1}, {'subtotal_cents':1}, {'shipping_method':None}, {'discount_cents':4000}])
def test_invalid_orders_refused_before_network(changes):
    with pytest.raises(ValueError):
        client(lambda r:pytest.fail('network called')).create_order(order(**changes), request_id='key')


@pytest.mark.parametrize('resource', ['../orders', 'ORDER?redirect=evil', 'https://evil.com', ''])
def test_ids_cannot_change_request_destination(resource):
    with pytest.raises(ValueError): client(lambda r:pytest.fail('network called')).get_order(resource)


@pytest.mark.parametrize('key', [None, '', 'a'*39, 'newline\n', 'é'])
@pytest.mark.parametrize('operation', ['create', 'capture', 'refund'])
def test_bad_request_id_rejected(key, operation):
    api = client(lambda r:pytest.fail('network called'))
    with pytest.raises(ValueError):
        if operation == 'create': api.create_order(order(), request_id=key)
        elif operation == 'capture': api.capture_order('ORDER', request_id=key)
        else: api.refund_capture('CAPTURE', amount_cents=1, currency='USD', request_id=key)


def test_refund_and_resource_endpoints():
    paths = []
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        paths.append(request.url.path)
        if request.method == 'POST':
            assert json.loads(request.content) == {'amount':{'currency_code':'USD','value':'0.01'}}
            assert request.headers['paypal-request-id'] == 'refund-key'
        return httpx.Response(200, json={'id':'RESOURCE'})
    api = client(handler)
    api.refund_capture('CAPTURE', amount_cents=1, currency='USD', request_id='refund-key')
    api.get_capture('CAPTURE'); api.get_refund('REFUND'); api.get_order('ORDER')
    assert paths == ['/v2/payments/captures/CAPTURE/refund', '/v2/payments/captures/CAPTURE',
                     '/v2/payments/refunds/REFUND', '/v2/checkout/orders/ORDER']
    with pytest.raises(ValueError): api.refund_capture('CAPTURE', amount_cents=1, currency='CAD', request_id='key')
    with pytest.raises(ValueError): api.refund_capture('CAPTURE', amount_cents=0, currency='USD', request_id='key')


def webhook_headers():
    return {'PayPal-Transmission-Id':'transmission', 'PayPal-Transmission-Time':'2026-10-04T00:00:00Z',
            'PayPal-Cert-Url':'https://api.sandbox.paypal.com/v1/notifications/certs/CERT',
            'PayPal-Auth-Algo':'SHA256withRSA', 'PayPal-Transmission-Sig':'signature'}


@pytest.mark.parametrize('result,expected', [('SUCCESS',True), ('FAILURE',False)])
def test_official_webhook_verification(result, expected):
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        assert request.url.path == '/v1/notifications/verify-webhook-signature'
        body = json.loads(request.content)
        assert body['webhook_id'] == 'WEBHOOK'
        assert body['webhook_event'] == {'id':'EVENT'}
        assert body['transmission_sig'] == 'signature'
        return httpx.Response(200, json={'verification_status':result})
    assert client(handler).verify_webhook(webhook_headers(), {'id':'EVENT'}) is expected


def test_webhook_missing_headers_fail_closed():
    assert not client(lambda r:pytest.fail('network called')).verify_webhook({}, {'id':'EVENT'})


def test_webhook_outage_is_retryable():
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        return httpx.Response(503, json={})
    with pytest.raises(PayPalRetryableError):
        client(handler, sleeper=lambda _:None).verify_webhook(webhook_headers(), {'id':'EVENT'})


def test_webhook_needs_app_id():
    with pytest.raises(PayPalConfigurationError):
        client(lambda r:pytest.fail('network called'), replace(config(), paypal_webhook_id=None)).verify_webhook(webhook_headers(), {})


@pytest.mark.parametrize('kind', [None, [], 42])
def test_malformed_oauth_response_is_retryable(kind):
    def handler(request):
        return httpx.Response(200, json={'access_token':'token', 'token_type':kind, 'expires_in':300})
    with pytest.raises(PayPalRetryableError): client(handler).get_order('ORDER')


@pytest.mark.parametrize('status', [[], {}])
def test_malformed_verification_response_is_retryable(status):
    def handler(request):
        if request.url.path == '/v1/oauth2/token': return token()
        return httpx.Response(200, json={'verification_status':status})
    with pytest.raises(PayPalRetryableError): client(handler).verify_webhook(webhook_headers(), {'id':'EVENT'})
