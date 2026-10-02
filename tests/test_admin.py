from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.admin_auth as admin_auth
from app.admin import variant_values
from app.audit import record_audit
from app.db import Base
from app.fulfillment.printful import PrintfulClient
from app.models import AuditLog
from app.settings import Settings


def base_config(**overrides):
    data = dict(
        app_env="development",
        public_base_url="https://blackmetalbuddha.com",
        database_url="sqlite://",
        phase1_api_enabled=False,
        square_environment="sandbox",
        square_api_version="2026-09-16",
        square_access_token=None,
        square_location_id=None,
        square_webhook_signature_key=None,
        square_webhook_notification_url=None,
        printful_token=None,
        printful_store_id=None,
        printful_mode="disabled",
        printful_webhook_secret_key=None,
        printful_webhook_public_key=None,
        phase0_5_approved=False,
        email_mode="disabled",
        smtp_host=None,
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        email_from=None,
        printful_confirm_enabled=False,
    )
    data.update(overrides)
    return Settings(**data)


def test_admin_auth_and_csrf(monkeypatch):
    fake = SimpleNamespace(
        admin_enabled=True,
        owner_console_enabled=True,
        admin_username="owner",
        admin_password="secret",
        app_secret_key="csrf-secret",
    )
    monkeypatch.setattr(admin_auth, "settings", fake)

    actor = admin_auth.require_admin(HTTPBasicCredentials(username="owner", password="secret"))
    assert actor == "owner"

    token = admin_auth.csrf_token("refund", "BMB-ABC")
    admin_auth.verify_csrf(token, "refund", "BMB-ABC")
    with pytest.raises(HTTPException) as exc:
        admin_auth.verify_csrf(token, "refund", "BMB-OTHER")
    assert exc.value.status_code == 403


def test_variant_values_require_printful_mapping_when_sellable():
    with pytest.raises(ValueError):
        variant_values({
            "size": "M",
            "color": "Black",
            "price": "32.00",
            "active": "on",
            "sellable": "on",
        })

    values = variant_values({
        "size": "m",
        "color": "Black",
        "price": "32.00",
        "active": "on",
        "sellable": "on",
        "printful_product_id": "1000",
        "printful_variant_id": "4011",
    })
    assert values["size"] == "M"
    assert values["retail_price_cents"] == 3200
    assert values["sellable"] is True


def test_audit_log_is_persisted():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        record_audit(
            session,
            actor="owner",
            action="test_action",
            object_type="order",
            object_id="BMB-TEST",
            details={"safe": True},
        )
        row = session.scalar(select(AuditLog))
        assert row.actor == "owner"
        assert row.action == "test_action"
        assert '"safe": true' in row.details_json.lower()


def test_production_checkout_requires_all_gates():
    cfg = base_config(
        app_env="production",
        phase1_api_enabled=True,
        production_checkout_enabled=True,
        production_canary_approved=False,
        production_catalog_approved=True,
        production_catalog_fingerprint="a" * 64,
        phase0_5_approved=True,
        square_environment="production",
        square_access_token="sq",
        square_location_id="loc",
        square_webhook_signature_key="wh",
        square_webhook_notification_url="https://blackmetalbuddha.com/api/v1/webhooks/square",
        printful_mode="production",
        printful_confirm_enabled=True,
        printful_token="pf",
        printful_store_id="store",
        printful_webhook_secret_key="aa" * 32,
        email_mode="smtp",
        smtp_host="smtp.example",
        email_from="orders@example.com",
        database_url="postgresql+psycopg://example",
        app_secret_key="secret",
        admin_username="owner",
        admin_password="password",
    )
    with pytest.raises(ValueError) as exc:
        cfg.validate_safety()
    assert "PRODUCTION_CANARY_APPROVED" in str(exc.value)


def test_production_checkout_can_pass_only_when_every_gate_is_explicit():
    cfg = base_config(
        app_env="production",
        phase1_api_enabled=True,
        production_checkout_enabled=True,
        production_canary_approved=True,
        production_catalog_approved=True,
        production_catalog_fingerprint="a" * 64,
        phase0_5_approved=True,
        square_environment="production",
        square_access_token="sq",
        square_location_id="loc",
        square_webhook_signature_key="wh",
        square_webhook_notification_url="https://blackmetalbuddha.com/api/v1/webhooks/square",
        printful_mode="production",
        printful_confirm_enabled=True,
        printful_token="pf",
        printful_store_id="store",
        printful_webhook_secret_key="aa" * 32,
        email_mode="smtp",
        smtp_host="smtp.example",
        email_from="orders@example.com",
        database_url="postgresql+psycopg://example",
        app_secret_key="secret",
        admin_username="owner",
        admin_password="password",
        support_email="support@example.com",
    )
    cfg.validate_safety()


def test_printful_cancel_uses_documented_v1_endpoint():
    seen = {}

    def handler(request: httpx.Request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"result": {"id": 777, "status": "canceled"}})

    cfg = base_config(printful_token="token", printful_store_id="store")
    client = PrintfulClient(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = client.cancel_order("@BMB-TEST")
    assert result["status"] == "canceled"
    assert seen == {"method": "DELETE", "path": "/orders/@BMB-TEST"}
