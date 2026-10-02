from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.api_phase1 as api
from app.main import app
from app.payments.square import verify_square_webhook
from app.fulfillment.printful import verify_printful_webhook
from app.schemas import AddressIn, CreateOrderIn


@pytest.mark.parametrize('provider', ['square', 'printful'])
@pytest.mark.parametrize('body', [b'{', b'[]', b'null', b'{"type": []}', b'{"event_id":"invalid-data", "data": []}'])
def test_authenticated_malformed_webhooks_are_client_errors(monkeypatch, provider, body):
    monkeypatch.setattr(api, 'verify_square_webhook', lambda *_: True)
    monkeypatch.setattr(api, 'verify_printful_webhook', lambda *_: True)
    with TestClient(app) as client:
        response = client.post('/api/v1/webhooks/' + provider, content=body)
    assert response.status_code == 400, response.text
    assert isinstance(response.json()['detail'], str)


def test_nonascii_webhook_signatures_are_rejected_without_exceptions():
    assert not verify_square_webhook(b'{}', 'é', signature_key='secret', notification_url='https://example.com')
    assert not verify_printful_webhook(b'{}', 'é', secret_key_hex='aa' * 32)


def address(**overrides):
    value = {'name': 'Buyer', 'email': 'buyer@example.com', 'address1': '1 Test St',
             'city': 'Denver', 'state': 'CO', 'postal_code': '80202', 'country_code': 'US'}
    value.update(overrides)
    return value


@pytest.mark.parametrize(('field', 'value'), [('name', '   '), ('address1', '\t'), ('city', ' '),
                                              ('email', 'invalid'), ('email', 'a@b\r\nBcc:x@y')])
def test_invalid_recipient_data_is_rejected_before_providers(field, value):
    with pytest.raises(ValidationError):
        AddressIn(**address(**{field: value}))


def test_duplicate_skus_cannot_bypass_per_variant_quantity_limit():
    with pytest.raises(ValidationError, match='Each SKU'):
        CreateOrderIn(recipient=address(), items=[{'sku': 'TEST', 'quantity': 10}, {'sku': 'TEST', 'quantity': 10}])


def test_address_normalization_preserves_real_data():
    result = AddressIn(**address(name=' Buyer ', state=' co ', country_code=' us '))
    assert result.name == 'Buyer'
    assert result.state == 'CO'
    assert result.country_code == 'US'


@pytest.mark.parametrize('status', [[], {}, 1, None, 'UNKNOWN'])
def test_invalid_refund_status_is_a_client_error(monkeypatch, status):
    monkeypatch.setattr(api, 'verify_square_webhook', lambda *_: True)
    with TestClient(app) as client:
        response = client.post('/api/v1/webhooks/square', json={
            'event_id': 'INVALID-REFUND-STATUS', 'type': 'refund.updated',
            'data': {'object': {'refund': {'id': 'REF-INVALID', 'status': status}}}})
    assert response.status_code == 400
    assert response.json()['detail'] == 'Invalid Square refund status'
