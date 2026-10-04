"""Server pricing inputs for the approved PayPal migration (mocked providers)."""
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from app.fulfillment.printful import PrintfulClient, PrintfulConfigurationError
from app.settings import settings
from app.tax import TaxConfigurationError, calculate_tax_cents
from app.payments.paypal_checkout import prepare_paypal_checkout
from app.payments.paypal import PayPalRetryableError
from app.orders import OrderError, set_shipping_rate
from app.models import Order
from app.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_reconcile import create_test_order


def make_order(**kwargs):
    value = dict(order_number='BMB-QUOTE', currency='USD', shipping_method='STANDARD',
        subtotal_cents=3500, discount_cents=0, shipping_cents=500, tax_cents=0,
        total_cents=4000, customer_name='Buyer', email='buyer@example.com', phone=None,
        ship_address1='1 Test St', ship_address2=None, ship_city='Canon City',
        ship_state='CO', ship_postal_code='81212', ship_country='US',
        items=[SimpleNamespace(id=1, sku_snapshot='BMB-LOTUS-L', quantity=1,
            unit_price_cents=3500, printful_product_id_snapshot='477390424',
            printful_variant_id_snapshot='123456')])
    return SimpleNamespace(**(value | kwargs))


def pf_client(handler):
    config = replace(settings, printful_token='test-token', printful_store_id='18844948',
                     printful_mode='disabled')
    return PrintfulClient(config, httpx.Client(transport=httpx.MockTransport(handler)))


def costs(**kwargs):
    value = dict(currency='USD', subtotal='20.00', discount='0.00', shipping='5.00',
                 tax='1.08', vat='0.00', total='26.08')
    return value | kwargs


def test_printful_quote_uses_saved_artwork_retail_prices_and_no_order_creation():
    calls = []
    order = make_order()
    def handler(request):
        calls.append(request)
        assert request.url == 'https://api.printful.com/orders/estimate-costs'
        assert request.method == 'POST'
        assert request.headers['x-pf-store-id'] == '18844948'
        body = json.loads(request.content)
        assert body['shipping'] == 'STANDARD'
        assert body['recipient']['state_code'] == 'CO'
        assert body['recipient']['zip'] == '81212'
        assert body['items'] == [{'sync_variant_id':123456, 'quantity':1,
            'external_id':'BMB-QUOTE-1', 'retail_price':'35.00'}]
        assert body['retail_costs'] == {'currency':'USD', 'subtotal':'35.00',
                                      'discount':'0.00', 'shipping':'5.00'}
        return httpx.Response(200, json={'code':200, 'result':{'costs':costs()}})
    result = pf_client(handler).estimate_order_costs(order)
    assert result['costs']['tax'] == '1.08'
    assert result['costs']['total'] == '26.08'
    assert len(calls) == 1
    assert order.tax_cents == 0 and order.total_cents == 4000


@pytest.mark.parametrize('changes', [{'shipping_method':None}, {'currency':'CAD'},
    {'ship_country':'GB'}])
def test_bad_quote_inputs_fail_before_http(changes):
    with pytest.raises(PrintfulConfigurationError):
        pf_client(lambda r:pytest.fail('HTTP called')).estimate_order_costs(make_order(**changes))


@pytest.mark.parametrize('field', ['currency', 'subtotal', 'discount', 'shipping', 'tax', 'vat', 'total'])
def test_incomplete_quote_is_not_silent_zero(field):
    data = costs(); del data[field]
    def handler(request): return httpx.Response(200, json={'result':{'costs':data}})
    with pytest.raises(PrintfulConfigurationError): pf_client(handler).estimate_order_costs(make_order())


@pytest.mark.parametrize('overrides', [{'currency':'CAD'}, {'tax':'NaN'}, {'tax':'Infinity'},
    {'tax':'-1.00'}, {'tax':'1.001'}, {'tax':True}, {'total':'1.00'},
    {'calculation_status':'calculating'}, {'tax':None}])
def test_invalid_or_pending_quote_is_rejected(overrides):
    def handler(request): return httpx.Response(200, json={'result':{'costs':costs(**overrides)}})
    with pytest.raises(PrintfulConfigurationError): pf_client(handler).estimate_order_costs(make_order())


@pytest.mark.parametrize('result', [None, [], {'costs':None}, {'costs':[]}])
def test_invalid_quote_structure_is_rejected(result):
    def handler(request): return httpx.Response(200, json={'result':result})
    with pytest.raises(PrintfulConfigurationError): pf_client(handler).estimate_order_costs(make_order())


def test_provider_outage_propagates_without_creating_order():
    def handler(request): return httpx.Response(503, json={})
    with pytest.raises(httpx.HTTPStatusError): pf_client(handler).estimate_order_costs(make_order())


def test_zero_tax_and_canadian_vat_are_provider_supplied():
    def handler(request):
        return httpx.Response(200, json={'result':{'costs':costs(tax=0, vat=2.5, total=27.5)}})
    result = pf_client(handler).estimate_order_costs(make_order(ship_country='CA', ship_state='ON',
                                                             ship_postal_code='M5V 2T6'))
    assert result['costs']['tax'] == 0 and result['costs']['vat'] == 2.5


def checkout_config(**overrides):
    value = dict(app_env='development', paypal_client_id='client', paypal_client_secret='secret',
                 paypal_merchant_id='MERCHANT', paypal_environment='sandbox',
                 checkout_tax_mode='printful_quote', checkout_tax_policy_approved=True,
                 printful_catalog_sync_enabled=False)
    return replace(settings, **(value | overrides))


class EstimateProvider:
    calls = 0
    def estimate_order_costs(self, order):
        self.calls += 1
        return {'costs':costs()}


@pytest.fixture
def checkout_database(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "checkout.db"}',
                           connect_args={'check_same_thread':False, 'timeout':10})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as session:
        order = create_test_order(session)
        order.items[0].unit_price_cents = 3500
        order.items[0].line_total_cents = 3500
        order.subtotal_cents = 3500
        order.shipping_cents = 500
        order.shipping_method = 'STANDARD'
        order.shipping_quoted_at = datetime.now(timezone.utc)
        order.total_cents = 4000
        session.commit()
        identity = order.id
    yield factory, identity
    engine.dispose()


class CheckoutProvider:
    def __init__(self, order, config=None):
        self.config = config or checkout_config()
        self.keys = []
        self.remote = {'id':'PPORDER', 'intent':'CAPTURE', 'status':'CREATED',
            'purchase_units':[{'reference_id':order.order_number,'custom_id':order.id,
                'payee':{'merchant_id':'MERCHANT'},
                'amount':{'currency_code':'USD','value':'41.08'},
                'shipping':{'name':{'full_name':order.customer_name}, 'address':{
                    'address_line_1':order.ship_address1, 'admin_area_2':order.ship_city,
                    'admin_area_1':order.ship_state, 'postal_code':order.ship_postal_code,
                    'country_code':order.ship_country}}}],
            'links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=PPORDER'}]}
    def create_order(self, order, *, request_id):
        self.keys.append(request_id)
        assert order.total_cents == 4108
        return self.remote
    def get_order(self, identity):
        assert identity == 'PPORDER'
        return self.remote


@pytest.mark.parametrize('value,expected', [(costs(),108), (costs(tax='0.00',total='25.00'),0),
                                         (costs(tax='0.00',vat='2.50',total='27.50'),250)])
def test_accountant_approved_policy_uses_actual_printful_quote(value, expected):
    provider = SimpleNamespace(estimate_order_costs=lambda _: {'costs':value})
    order = make_order()
    assert calculate_tax_cents(order, config=checkout_config(), client=provider) == expected
    assert json.loads(order.printful_estimate_json)['costs'] == value
    assert order.printful_estimated_at is not None


@pytest.mark.parametrize('changes', [{'checkout_tax_mode':'disabled'},
                                    {'checkout_tax_policy_approved':False}])
def test_missing_tax_configuration_refuses_checkout(changes):
    with pytest.raises(TaxConfigurationError):
        calculate_tax_cents(make_order(), config=checkout_config(**changes),
            client=SimpleNamespace(estimate_order_costs=lambda _:pytest.fail('provider called')))


def test_checkout_uses_server_tax_total_and_one_frozen_attempt(checkout_database):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order,identity); provider = CheckoutProvider(order); estimate = EstimateProvider()
        prepare_paypal_checkout(session, order, config=provider.config, client=provider, printful_client=estimate)
        key = order.paypal_create_request_id
        assert order.payment_provider == 'paypal' and order.paypal_order_id == 'PPORDER'
        assert order.tax_cents == 108 and order.total_cents == 4108
        assert json.loads(order.paypal_snapshot)['total_cents'] == 4108
        assert prepare_paypal_checkout(session, order, config=provider.config, client=provider,
                                       printful_client=estimate) == order.paypal_checkout_url
        assert provider.keys == [key] and estimate.calls == 1


def test_unknown_create_response_reuses_key_and_quote_after_restart(checkout_database):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order,identity); provider = CheckoutProvider(order); estimate = EstimateProvider()
        original = provider.create_order
        def lost(order, *, request_id):
            provider.keys.append(request_id)
            raise PayPalRetryableError('Response lost')
        provider.create_order = lost
        with pytest.raises(PayPalRetryableError):
            prepare_paypal_checkout(session, order, config=provider.config, client=provider, printful_client=estimate)
    provider.create_order = original
    with factory() as session:
        prepare_paypal_checkout(session, session.get(Order,identity), config=provider.config,
                                client=provider, printful_client=estimate)
    assert len(provider.keys) == 2 and len(set(provider.keys)) == 1 and estimate.calls == 1


@pytest.mark.parametrize('field,value', [('ship_city','Changed'), ('tax_cents',0),
                                      ('shipping_cents',1), ('subtotal_cents',1)])
def test_frozen_attempt_refuses_changed_address_or_pricing(checkout_database, field, value):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order,identity); provider = CheckoutProvider(order)
        prepare_paypal_checkout(session, order, config=provider.config, client=provider,
                                printful_client=EstimateProvider())
        setattr(order,field,value); session.commit()
        with pytest.raises(OrderError, match='changed'):
            prepare_paypal_checkout(session, order, config=provider.config, client=provider,
                                    printful_client=EstimateProvider())


def test_shipping_cannot_change_during_a_paypal_attempt(checkout_database):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order,identity); provider = CheckoutProvider(order)
        prepare_paypal_checkout(session, order, config=provider.config, client=provider,
                                printful_client=EstimateProvider())
        with pytest.raises(OrderError):
            set_shipping_rate(session,order,shipping_method='EXPRESS',shipping_cents=1000,currency='USD')


@pytest.mark.parametrize('case', ['amount','merchant','reference','shipping','currency','link'])
def test_provider_binding_or_approval_link_mismatch_cannot_attach(checkout_database, case):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order,identity); provider = CheckoutProvider(order)
        unit = provider.remote['purchase_units'][0]
        if case == 'amount': unit['amount']['value'] = '0.01'
        elif case == 'merchant': unit['payee']['merchant_id'] = 'OTHER'
        elif case == 'reference': unit['reference_id'] = 'OTHER'
        elif case == 'shipping': unit['shipping']['address']['country_code'] = 'CA'
        elif case == 'currency': unit['amount']['currency_code'] = 'CAD'
        else: provider.remote['links'][0]['href'] = 'https://evil.example/checkoutnow?token=PPORDER'
        with pytest.raises(OrderError):
            prepare_paypal_checkout(session, order, config=provider.config, client=provider,
                                    printful_client=EstimateProvider())
        session.refresh(order)
        assert order.paypal_order_id is None and order.payment_state == 'PENDING'


def test_concurrent_requests_reserve_one_durable_operation(checkout_database):
    factory, identity = checkout_database
    with factory() as session: provider = CheckoutProvider(session.get(Order,identity))
    estimate = EstimateProvider()
    def run():
        with factory() as session:
            return prepare_paypal_checkout(session,session.get(Order,identity),config=provider.config,
                                           client=provider,printful_client=estimate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(lambda _:run(),range(2)))) == 1
    assert len(set(provider.keys)) == 1 and estimate.calls == 1

from fastapi.testclient import TestClient
import app.api_phase1 as api
from app.main import app
from app.rate_limit import limiter
from app.orders import verify_order_access


def test_order_token_is_hashed_and_not_reissued(checkout_database):
    factory, identity = checkout_database
    with factory() as session:
        order = session.get(Order, identity)
        assert order.order_access_token_hash is not None
        assert api._order_out(order).order_token is None
        with pytest.raises(OrderError): verify_order_access(order, 'foreign')


@pytest.mark.parametrize('token', [None, 'foreign'])
def test_paypal_checkout_requires_owner_token(checkout_database, monkeypatch, token):
    factory, identity = checkout_database
    with factory() as session: number = session.get(Order,identity).order_number
    def db():
        with factory() as session: yield session
    app.dependency_overrides[api.db_session] = db
    monkeypatch.setattr(api, 'settings', checkout_config(phase1_api_enabled=True))
    monkeypatch.setattr(api, "limiter", type(limiter)())
    try:
        with TestClient(app) as browser:
            response = browser.post('/api/phase1/orders/'+number+'/paypal-checkout',
                                    headers={'X-BMB-Order-Token':token} if token else {})
        assert response.status_code == 403
    finally: app.dependency_overrides.clear()


@pytest.mark.parametrize('changes', [{'currency':'CAD'}, {'ship_country':'GB'},
                                     {'shipping_quoted_at':datetime.now(timezone.utc)-timedelta(hours=1)}])
def test_checkout_refuses_invalid_inputs_before_provider(checkout_database, changes):
    factory, identity = checkout_database
    with factory() as session:
        order=session.get(Order,identity)
        for field,value in changes.items(): setattr(order,field,value)
        session.commit()
        with pytest.raises(OrderError):
            prepare_paypal_checkout(session,order,config=checkout_config(),
                client=SimpleNamespace(create_order=lambda **_:pytest.fail('provider called')),
                printful_client=EstimateProvider())


def test_unknown_create_cannot_retry_beyond_key_retention(checkout_database):
    factory,identity=checkout_database
    with factory() as session:
        order=session.get(Order,identity); provider=CheckoutProvider(order)
        def lost(*_, **kwargs): raise PayPalRetryableError('lost')
        provider.create_order=lost
        with pytest.raises(PayPalRetryableError):
            prepare_paypal_checkout(session,order,config=provider.config,client=provider,printful_client=EstimateProvider())
        order.paypal_create_requested_at=datetime.now(timezone.utc)-timedelta(hours=7)
        session.commit()
        with pytest.raises(OrderError,match='reconciliation'):
            prepare_paypal_checkout(session,order,config=provider.config,client=provider,printful_client=EstimateProvider())


def test_shipping_and_square_cannot_access_a_new_order_without_token(checkout_database, monkeypatch):
    factory,identity=checkout_database
    with factory() as session: number=session.get(Order,identity).order_number
    def db():
        with factory() as session: yield session
    app.dependency_overrides[api.db_session]=db
    monkeypatch.setattr(api,'settings',checkout_config(phase1_api_enabled=True))
    monkeypatch.setattr(api,'limiter',type(limiter)())
    try:
        with TestClient(app) as browser:
            assert browser.get('/api/v1/orders/'+number+'/shipping-rates').status_code == 403
            assert browser.post('/api/v1/orders/'+number+'/shipping',json={'shipping':'STANDARD'}).status_code == 403
            assert browser.post('/api/v1/orders/'+number+'/square-checkout').status_code == 403
    finally: app.dependency_overrides.clear()


def test_stale_shipping_object_cannot_mutate_an_active_attempt(checkout_database):
    factory,identity=checkout_database
    with factory() as stale, factory() as active:
        stale_order=stale.get(Order,identity)
        order=active.get(Order,identity);provider=CheckoutProvider(order)
        prepare_paypal_checkout(active,order,config=provider.config,client=provider,printful_client=EstimateProvider())
        with pytest.raises(OrderError):
            set_shipping_rate(stale,stale_order,shipping_method='EXPRESS',shipping_cents=1000,currency='USD')


@pytest.mark.parametrize('value',['1.00000000000000000000000000001','1e1000000'])
def test_quote_does_not_round_tiny_fractions_or_allocate_unbounded_integers(value):
    def handler(request): return httpx.Response(200,json={'result':{'costs':costs(tax=value,total=value)}})
    with pytest.raises(PrintfulConfigurationError): pf_client(handler).estimate_order_costs(make_order())
