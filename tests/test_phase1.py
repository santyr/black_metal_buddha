import base64
import hashlib
import hmac
import json

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.fulfillment.printful import PrintfulClient, verify_printful_webhook
from app.jobs import process_email_job
from app.models import Job, Order, ProductVariant, Refund
from app.orders import (
    create_order,
    mark_paid_and_enqueue,
    set_shipping_rate,
    sync_square_pricing,
)
from app.payments.square import SquareClient, verify_square_webhook
from app.refunds import request_refund
from app.schemas import CreateOrderIn
from app.settings import Settings


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session


def config(**overrides):
    data = dict(
        app_env="development",
        public_base_url="https://blackmetalbuddha.com",
        database_url="sqlite://",
        phase1_api_enabled=True,
        square_environment="sandbox",
        square_api_version="2026-09-16",
        square_access_token="sq-token",
        square_location_id="LOC",
        square_webhook_signature_key="square-secret",
        square_webhook_notification_url="https://example.com/api/v1/webhooks/square",
        printful_token="pf-token",
        printful_store_id="123",
        printful_mode="draft",
        printful_webhook_secret_key="aa" * 32,
        printful_webhook_public_key=None,
        phase0_5_approved=False,
        email_mode="console",
        smtp_host=None,
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        email_from=None,
    )
    data.update(overrides)
    return Settings(**data)


def order_input():
    return CreateOrderIn(
        recipient={
            "name": "Test Buyer",
            "email": "buyer@example.com",
            "address1": "1 Test Way",
            "city": "Denver",
            "state": "CO",
            "postal_code": "80202",
            "country_code": "US",
        },
        items=[{"sku": "BMB-LOTUS-BLK-M", "quantity": 2}],
    )


def seed_variant(session):
    variant = ProductVariant(
        product_slug="lotus-of-the-void",
        sku="BMB-LOTUS-BLK-M",
        size="M",
        color="Black",
        currency="USD",
        retail_price_cents=3200,
        active=True,
        sellable=True,
        printful_product_id="1000",
        printful_variant_id="4011",
    )
    session.add(variant)
    session.commit()
    return variant


def select_test_shipping(session, order, cents=599):
    set_shipping_rate(
        session,
        order,
        shipping_method="STANDARD",
        shipping_cents=cents,
        currency="USD",
    )


def square_order_payload(order, tax_cents=300):
    return {
        "id": "SQORDER",
        "reference_id": order.order_number,
        "line_items": [
            {
                "name": item.name_snapshot,
                "quantity": str(item.quantity),
                "base_price_money": {
                    "amount": item.unit_price_cents,
                    "currency": order.currency,
                },
            }
            for item in order.items
        ],
        "total_service_charge_money": {
            "amount": order.shipping_cents,
            "currency": order.currency,
        },
        "total_discount_money": {"amount": 0, "currency": order.currency},
        "total_tax_money": {"amount": tax_cents, "currency": order.currency},
        "total_money": {
            "amount": order.subtotal_cents + order.shipping_cents + tax_cents,
            "currency": order.currency,
        },
    }


def test_order_snapshots_server_price(session):
    seed_variant(session)
    order = create_order(session, order_input())
    assert order.subtotal_cents == 6400
    assert order.total_cents == 6400
    assert order.items[0].sku_snapshot == "BMB-LOTUS-BLK-M"
    assert order.items[0].unit_price_cents == 3200
    assert order.printful_external_id == order.order_number


def test_paid_transition_enqueues_once(session):
    seed_variant(session)
    order = create_order(session, order_input())
    assert mark_paid_and_enqueue(session, order, square_payment_id="PAY1") is True
    assert order.payment_state == "COMPLETED"
    jobs = session.scalars(select(Job)).all()
    assert {job.job_type for job in jobs} == {
        "SUBMIT_PRINTFUL_ORDER",
        "SEND_ORDER_CONFIRMATION",
    }

    assert mark_paid_and_enqueue(session, order, square_payment_id="PAY1") is False
    assert len(session.scalars(select(Job)).all()) == 2


def test_square_signature():
    body = b'{"event_id":"evt"}'
    url = "https://example.com/api/v1/webhooks/square"
    key = "secret"
    expected = base64.b64encode(
        hmac.new(key.encode(), url.encode() + body, hashlib.sha256).digest()
    ).decode()
    assert verify_square_webhook(body, expected, signature_key=key, notification_url=url)
    assert not verify_square_webhook(body + b"x", expected, signature_key=key, notification_url=url)


def test_square_payment_link_payload_includes_shipping_and_auto_tax(session):
    seed_variant(session)
    order = create_order(session, order_input())
    select_test_shipping(session, order)
    captured = {}

    def handler(request: httpx.Request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"payment_link": {
                "id": "LINK", "order_id": "SQORDER", "url": "https://square.link/u/test"
            }},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    link = SquareClient(config(), client=client).create_payment_link(order)
    assert link["id"] == "LINK"
    payload = captured["json"]
    assert payload["order"]["reference_id"] == order.order_number
    assert payload["order"]["pricing_options"]["auto_apply_taxes"] is True
    assert payload["order"]["line_items"][0]["base_price_money"]["amount"] == 3200
    assert payload["checkout_options"]["shipping_fee"]["charge"]["amount"] == 599
    assert payload["checkout_options"]["ask_for_shipping_address"] is False
    fulfillment = payload["order"]["fulfillments"][0]
    assert fulfillment["type"] == "SHIPMENT"
    assert fulfillment["shipment_details"]["recipient"]["address"]["postal_code"] == "80202"


def test_square_pricing_sync_accepts_square_tax(session):
    seed_variant(session)
    order = create_order(session, order_input())
    select_test_shipping(session, order, 599)
    sync_square_pricing(session, order, square_order_payload(order, tax_cents=511))
    assert order.shipping_cents == 599
    assert order.tax_cents == 511
    assert order.total_cents == 7510


def test_printful_shipping_rates_and_draft_payload(session):
    seed_variant(session)
    order = create_order(session, order_input())
    requests = []

    def handler(request: httpx.Request):
        if request.url.path == "/store/variants/4011":
            return httpx.Response(200, json={"code": 200, "result": {
                "id": 4011, "sync_product_id": 1000, "variant_id": 18500,
                "synced": True,
            }})
        requests.append((request.url.path, json.loads(request.content)))
        if request.url.path == "/v2/shipping-rates":
            return httpx.Response(
                200,
                json={"data": [{
                    "shipping": "STANDARD",
                    "shipping_method_name": "Flat Rate",
                    "rate": "5.99",
                    "currency": "USD",
                    "min_delivery_days": 4,
                    "max_delivery_days": 7,
                }]},
            )
        return httpx.Response(
            200,
            json={"code": 200, "result": {"id": 777, "external_id": order.order_number, "status": "draft"}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pf = PrintfulClient(config(), client=client)
    rates = pf.get_shipping_rates(order)
    assert rates[0]["rate_cents"] == 599
    shipping_item = requests[0][1]["order_items"][0]
    assert shipping_item == {"source": "catalog", "catalog_variant_id": 18500, "quantity": 2}
    set_shipping_rate(
        session,
        order,
        shipping_method=rates[0]["shipping"],
        shipping_cents=rates[0]["rate_cents"],
        currency=rates[0]["currency"],
    )

    data = pf.create_draft_order(order)
    assert data["status"] == "draft"
    assert requests[-1][0] == "/orders"
    draft_payload = requests[-1][1]
    assert draft_payload["shipping"] == "STANDARD"
    assert draft_payload["external_id"] == order.order_number
    item = draft_payload["items"][0]
    assert item["sync_variant_id"] == 4011
    assert "variant_id" not in item
    assert "source" not in item
    assert item["quantity"] == 2


def test_refund_service_records_completed_refund_and_email_job(session):
    seed_variant(session)
    order = create_order(session, order_input())
    order.payment_state = "COMPLETED"
    order.order_state = "PAID"
    order.square_payment_id = "PAY1"
    session.commit()

    class RefundClient:
        def refund_payment(self, **kwargs):
            assert kwargs["payment_id"] == "PAY1"
            assert kwargs["amount_cents"] == 1000
            return {"id": "REF1", "status": "COMPLETED"}

    refund = request_refund(
        session,
        order,
        amount_cents=1000,
        reason="Test refund",
        client=RefundClient(),
    )
    assert refund.square_refund_id == "REF1"
    assert order.refunded_cents == 1000
    assert order.refund_state == "PARTIAL"
    jobs = session.scalars(select(Job).where(Job.job_type.like("SEND_REFUND_CONFIRMATION:%"))).all()
    assert len(jobs) == 1


def test_email_job_dispatch(session):
    seed_variant(session)
    order = create_order(session, order_input())
    job = Job(job_type="SEND_ORDER_CONFIRMATION", order_id=order.id, state="PENDING")
    session.add(job)
    session.commit()

    class Sender:
        called = False

        def send_order_confirmation(self, received):
            assert received.order_number == order.order_number
            self.called = True

        def send_shipping_notification(self, received):
            raise AssertionError

        def send_refund_confirmation(self, received):
            raise AssertionError

    sender = Sender()
    process_email_job(session, job, config=config(), sender=sender)
    assert sender.called is True
    assert job.state == "COMPLETED"


def test_printful_signature():
    body = b'{"type":"order_updated"}'
    secret = bytes.fromhex("ab" * 32)
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    assert verify_printful_webhook(body, sig, secret_key_hex="ab" * 32)
    assert not verify_printful_webhook(body + b"x", sig, secret_key_hex="ab" * 32)


def test_production_printful_requires_phase0_5():
    cfg = config(printful_mode="production", phase0_5_approved=False)
    with pytest.raises(ValueError):
        cfg.validate_safety()
