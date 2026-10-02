from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.admin_auth as admin_auth
import app.api_phase1 as api
import app.main as main
from app.admin import money_to_cents


def test_admin_auth_challenge_survives_error_handler(monkeypatch):
    monkeypatch.setattr(admin_auth, 'settings', SimpleNamespace(admin_enabled=True))
    with TestClient(main.app) as client:
        response = client.get('/admin')
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Basic'


def test_api_errors_are_json_and_keep_retry_after(monkeypatch):
    monkeypatch.setattr(api, 'settings', replace(api.settings, phase1_api_enabled=True))
    def limited(*args, **kwargs):
        raise HTTPException(429, 'Please wait', headers={'Retry-After': '600'})
    monkeypatch.setattr(api, '_limit_customer_mutation', limited)
    with TestClient(main.app) as client:
        response = client.post('/api/v1/orders/BMB-UNKNOWN/square-checkout')
        missing = client.get('/api/v1/orders/BMB-UNKNOWN')
    assert response.status_code == 429
    assert response.json() == {'detail': 'Please wait'}
    assert response.headers['retry-after'] == '600'
    assert missing.status_code == 404
    assert missing.json() == {'detail': 'Order not found'}


@pytest.mark.parametrize('value', ['Infinity', '-Infinity', 'NaN', 'sNaN', '1e9999', '-0.001'])
def test_admin_rejects_nonfinite_or_out_of_range_prices(value):
    with pytest.raises(ValueError):
        money_to_cents(value)


@pytest.mark.parametrize(('state', 'fulfillment', 'refund', 'heading'), [
    ('SHIPPED', 'RETURNED', 'NONE', 'A shipment was returned.'),
    ('REFUNDED', 'NOT_STARTED', 'COMPLETED', 'Your payment has been refunded.'),
    ('FULFILLMENT_FAILED', 'FAILED', 'NONE', 'Your order needs attention.'),
    ('FULFILLMENT_HOLD', 'HOLD', 'NONE', 'Your order is on hold.'),
    ('IN_PRODUCTION', 'CANCELED', 'NONE', 'Fulfillment was canceled.'),
])
def test_order_status_reports_exceptions_before_normal_states(monkeypatch, state, fulfillment, refund, heading):
    order = SimpleNamespace(order_state=state, fulfillment_state=fulfillment, refund_state=refund,
                            is_canary=True, order_number='BMB-TEST')
    monkeypatch.setattr(main, 'get_order', lambda *_: order)
    monkeypatch.setattr(main.templates, 'TemplateResponse', lambda request, name, context: context)
    context = main.order_status(Request({'type': 'http', 'method': 'GET', 'path': '/orders/BMB-TEST'}), 'BMB-TEST')
    assert context['status_heading'] == heading


def test_checkout_api_uses_catalog_prices_and_reuses_checkout(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import Base
    from app.models import ProductVariant

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        session.add(ProductVariant(product_slug='lotus-of-the-void', sku='AUDIT-M', size='M',
                                   color='Black', currency='USD', retail_price_cents=3200,
                                   active=True, sellable=True, printful_product_id='1', printful_variant_id='2'))
        session.commit()
    def session_dependency():
        with Session() as session:
            yield session
    monkeypatch.setattr(api, 'settings', replace(api.settings, phase1_api_enabled=True))
    class Shipping:
        def get_shipping_rates(self, order):
            return [{'shipping': 'STANDARD', 'name': 'Standard', 'rate_cents': 500, 'currency': 'USD'}]
    class Payments:
        calls = 0
        number = None
        def create_payment_link(self, order):
            self.__class__.calls += 1
            self.__class__.number = order.order_number
            return {'id': 'LINK-1', 'order_id': 'SQ-1', 'url': 'https://square.example/checkout'}
        def get_order(self, _):
            return {'reference_id': self.number,
                    'line_items': [{'name': 'Lotus of the Void', 'quantity': '2', 'base_price_money': {'amount': 3200, 'currency': 'USD'}}],
                    'total_service_charge_money': {'amount': 500, 'currency': 'USD'},
                    'total_tax_money': {'amount': 690, 'currency': 'USD'},
                    'total_money': {'amount': 7590, 'currency': 'USD'}}
    monkeypatch.setattr(api, 'PrintfulClient', Shipping)
    monkeypatch.setattr(api, 'SquareClient', Payments)
    monkeypatch.setattr(api, 'verify_square_webhook', lambda *_: True)
    main.app.dependency_overrides[api.db_session] = session_dependency
    try:
        with TestClient(main.app) as client:
            response = client.post('/api/v1/orders', json={
                'recipient': {'name': 'Audit Buyer', 'email': 'audit@example.com', 'address1': '1 Test St',
                              'city': 'Denver', 'state': 'CO', 'postal_code': '80202'},
                'items': [{'sku': 'AUDIT-M', 'quantity': 2, 'price_cents': 1}]})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data['subtotal_cents'] == 6400
            path = '/api/v1/orders/' + data['order_number']
            assert client.post(path + '/square-checkout').status_code == 409
            assert client.get(path + '/shipping-rates').json()[0]['rate_cents'] == 500
            assert client.post(path + '/shipping', json={'shipping': 'STANDARD'}).status_code == 200
            for _ in range(2):
                checkout = client.post(path + '/square-checkout')
                assert checkout.status_code == 200, checkout.text
                assert checkout.json()['total_cents'] == 7590
                assert checkout.json()['square_checkout_url'] == 'https://square.example/checkout'
            assert Payments.calls == 1
            for status in ('COMPLETED', 'FAILED'):
                event = {'event_id': 'EVENT-' + status, 'type': 'payment.updated',
                         'data': {'object': {'payment': {'id': 'PAY-1', 'order_id': 'SQ-1',
                                  'status': status, 'amount_money': {'amount': 7590, 'currency': 'USD'}}}}}
                webhook = client.post('/api/v1/webhooks/square', json=event)
                assert webhook.status_code == 200, webhook.text
            assert client.get(path).json()['payment_state'] == 'COMPLETED'
    finally:
        main.app.dependency_overrides.pop(api.db_session, None)
        engine.dispose()
