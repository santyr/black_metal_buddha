"""Provider contract checks derived from Printful's published v1/v2 schemas."""
import json

import httpx
import pytest

from app.fulfillment.printful import PrintfulClient, PrintfulConfigurationError, extract_printful_costs
from app.jobs import process_submit_printful_job
from app.reconcile import reconcile_printful_order
from tests.test_printful_confirmation import config, make_order


def test_saved_variant_worker_uses_draft_then_gated_confirmation_and_reuses_order():
    session, order, job = make_order()
    state = {"order": None}
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == f"/orders/@{order.order_number}":
            return httpx.Response(404 if state["order"] is None else 200,
                                  json={"result": state["order"]})
        if request.method == "POST" and request.url.path == "/orders":
            payload = json.loads(request.content)
            assert request.url.params["confirm"] == "false"
            assert request.url.params["update_existing"] == "false"
            assert payload["items"][0]["sync_variant_id"] == 4011
            assert payload["external_id"] == order.order_number
            state["order"] = {"id": 777, "external_id": order.order_number,
                              "status": "draft", "costs": {"currency": "USD", "total": "20.00"}}
            return httpx.Response(200, json={"result": state["order"]})
        if request.method == "POST" and request.url.path == f"/orders/@{order.order_number}/confirm":
            state["order"]["status"] = "pending"
            return httpx.Response(200, json={"result": state["order"]})
        return httpx.Response(400, json={"error": {"message": "Unsupported provider contract"}})

    try:
        pf = PrintfulClient(config(), client=httpx.Client(transport=httpx.MockTransport(handler)))
        process_submit_printful_job(session, job, config=config(), client=pf)
        assert job.state == "COMPLETED", job.last_error
        assert order.order_state == "IN_PRODUCTION"
        assert order.printful_cost_cents == 2000
        assert order.printful_confirmed_at is not None
        job.state = "PENDING"
        session.commit()
        process_submit_printful_job(session, job, config=config(), client=pf)
        assert job.state == "COMPLETED"
        assert [method for method, _ in requests].count("POST") == 2
    finally:
        session.close()


@pytest.mark.parametrize("variant", [
    {"id": 4011, "sync_product_id": 999, "variant_id": 18500, "synced": True},
    {"id": 4011, "sync_product_id": 1000, "variant_id": 18500, "synced": False},
    {"id": 4011, "sync_product_id": 1000, "variant_id": None, "synced": True},
])
def test_shipping_rejects_unusable_or_wrong_saved_variant(variant):
    session, order, _ = make_order()
    paths = []
    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"result": variant})
    try:
        pf = PrintfulClient(config(), client=httpx.Client(transport=httpx.MockTransport(handler)))
        with pytest.raises(PrintfulConfigurationError):
            pf.get_shipping_rates(order)
        assert paths == ["/store/variants/4011"]
    finally:
        session.close()


def test_saved_order_reconciliation_reads_embedded_shipments_and_epoch_timestamp():
    session, order, _ = make_order()
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == f"/orders/@{order.order_number}"
        return httpx.Response(200, json={"result": {
            "id": 777, "external_id": order.order_number, "status": "fulfilled",
            "shipments": [{"id": 123, "shipped_at": 1790899200,
                           "tracking_number": "TRACK123", "tracking_url": "https://carrier.example/123"}],
        }})
    try:
        pf = PrintfulClient(config(), client=httpx.Client(transport=httpx.MockTransport(handler)))
        assert reconcile_printful_order(session, order, client=pf) == "FULFILLED"
        session.refresh(order)
        assert len(order.shipments) == 1
        assert order.shipments[0].status == "SHIPPED"
        assert order.shipments[0].tracking_number == "TRACK123"
        assert order.shipments[0].shipped_at.isoformat().startswith("2026-10-02T00:00:00")
    finally:
        session.close()


def test_v1_costs_without_v2_status_are_ready_only_with_currency_and_total():
    assert extract_printful_costs({"costs": {"currency": "USD", "total": "20.00"}}) == ("done", "USD", 2000)
    assert extract_printful_costs({"costs": {"currency": None, "total": None}}) == ("calculating", None, None)


def test_async_unconfirmed_hold_does_not_mark_confirmation_complete():
    session, order, job = make_order()
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"result": {
            "id": 777, "status": "onhold", "costs": {"currency": None, "total": None},
        }})
    try:
        pf = PrintfulClient(config(), client=httpx.Client(transport=httpx.MockTransport(handler)))
        process_submit_printful_job(session, job, config=config(), client=pf)
        assert job.state == "PENDING"
        assert order.printful_confirmed_at is None
    finally:
        session.close()
