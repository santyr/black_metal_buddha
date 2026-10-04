from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.jobs import process_submit_printful_job
from app.models import Job, ProductVariant
from app.orders import create_order
from app.schemas import CreateOrderIn
from app.settings import Settings


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
        printful_mode="production",
        printful_webhook_secret_key="aa" * 32,
        printful_webhook_public_key=None,
        phase0_5_approved=True,
        email_mode="disabled",
        smtp_host=None,
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        email_from=None,
        printful_confirm_enabled=True,
    )
    data.update(overrides)
    return Settings(**data)


def make_order():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    variant = ProductVariant(
        product_slug="lotus-of-the-void",
        sku="CONFIRM-LOTUS-M",
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
    order = create_order(
        session,
        CreateOrderIn(
            recipient={
                "name": "Test Buyer",
                "email": "buyer@example.com",
                "address1": "1 Test Way",
                "city": "Denver",
                "state": "CO",
                "postal_code": "80202",
                "country_code": "US",
            },
            items=[{"sku": "CONFIRM-LOTUS-M", "quantity": 1}],
        ),
    )
    order.shipping_method = "STANDARD"
    order.shipping_cents = 500
    order.total_cents = 3700
    order.payment_state = "COMPLETED"
    order.order_state = "PAID"
    order.paid_at = datetime.now(timezone.utc)
    job = Job(job_type="SUBMIT_PRINTFUL_ORDER", order_id=order.id, state="PENDING")
    session.add(job)
    session.commit()
    return session, order, job


class ConfirmablePrintful:
    confirm_calls = 0

    def get_order_by_external_id(self, external_id):
        return {
            "id": 777,
            "external_id": external_id,
            "status": "draft",
            "costs": {
                "calculation_status": "done",
                "currency": "USD",
                "total": "20.00",
            },
        }

    def create_draft_order(self, order):
        raise AssertionError("existing draft should be reused")

    def confirm_order(self, external_id):
        self.confirm_calls += 1
        return {
            "id": 777,
            "external_id": external_id.lstrip("@"),
            "status": "pending",
            "costs": {
                "calculation_status": "done",
                "currency": "USD",
                "total": "20.00",
            },
        }


def test_production_confirmation_requires_both_gates():
    missing_sample = config(phase0_5_approved=False)
    try:
        missing_sample.validate_safety()
        assert False, "expected sample gate failure"
    except ValueError:
        pass

    missing_switch = config(printful_confirm_enabled=False)
    try:
        missing_switch.validate_safety()
        assert False, "expected confirmation switch failure"
    except ValueError:
        pass

    config().validate_safety()


def test_confirmation_happens_once_and_records_cost():
    session, order, job = make_order()
    try:
        pf = ConfirmablePrintful()
        process_submit_printful_job(session, job, config=config(), client=pf)
        assert job.state == "COMPLETED"
        assert pf.confirm_calls == 1
        assert order.printful_order_id == "777"
        assert order.printful_cost_cents == 2000
        assert order.printful_cost_currency == "USD"
        assert order.printful_confirmed_at is not None
        assert order.order_state == "IN_PRODUCTION"

        # Simulate a retry after a network ambiguity. Provider now says pending,
        # so the confirmation endpoint must not be called again.
        job.state = "PENDING"
        session.commit()

        class AlreadyConfirmed(ConfirmablePrintful):
            def get_order_by_external_id(self, external_id):
                data = super().get_order_by_external_id(external_id)
                data["status"] = "pending"
                return data

            def confirm_order(self, external_id):
                raise AssertionError("must not confirm an already-confirmed order")

        process_submit_printful_job(session, job, config=config(), client=AlreadyConfirmed())
        assert job.state == "COMPLETED"
    finally:
        session.close()


def test_cost_guard_permanently_blocks_overrun():
    session, order, job = make_order()
    try:
        class TooExpensive(ConfirmablePrintful):
            def get_order_by_external_id(self, external_id):
                data = super().get_order_by_external_id(external_id)
                data["costs"]["total"] = "99.00"
                return data

            def confirm_order(self, external_id):
                raise AssertionError("cost guard must prevent confirmation")

        process_submit_printful_job(session, job, config=config(), client=TooExpensive())
        assert job.state == "FAILED"
        assert order.order_state == "FULFILLMENT_FAILED"
        assert order.printful_cost_cents == 9900
        assert "exceeds customer order total" in (job.last_error or "")
    finally:
        session.close()


def test_calculating_costs_retry_without_confirmation():
    session, order, job = make_order()
    try:
        class Calculating(ConfirmablePrintful):
            def get_order_by_external_id(self, external_id):
                data = super().get_order_by_external_id(external_id)
                data["costs"] = {
                    "calculation_status": "calculating",
                    "currency": None,
                    "total": None,
                }
                return data

            def confirm_order(self, external_id):
                raise AssertionError("must wait for cost calculation")

        process_submit_printful_job(session, job, config=config(), client=Calculating())
        assert job.state == "PENDING"
        assert job.attempt_count == 1
        assert order.printful_confirmed_at is None
    finally:
        session.close()


def test_printful_funding_decline_holds_paid_order_and_reuses_external_id():
    import httpx
    session,order,job=make_order()
    order.payment_provider='paypal'
    class FundingDeclined(ConfirmablePrintful):
        lookups=[]
        def get_order_by_external_id(self,external_id):
            self.lookups.append(external_id)
            return super().get_order_by_external_id(external_id)
        def confirm_order(self,identity):
            self.confirm_calls+=1
            if self.confirm_calls==1:
                request=httpx.Request('POST','https://api.printful.com/orders/@test/confirm')
                raise httpx.HTTPStatusError('Funding declined',request=request,response=httpx.Response(402,request=request))
            return {'id':777,'status':'pending','costs':{'currency':'USD','subtotal':'15.00','discount':'0.00',
                'shipping':'5.00','tax':'1.00','vat':'0.00','total':'21.00','calculation_status':'done'}}
    provider=FundingDeclined()
    process_submit_printful_job(session,job,config=config(),client=provider)
    assert order.payment_state=='COMPLETED' and order.order_state=='FULFILLMENT_HOLD'
    assert job.state=='PENDING'
    process_submit_printful_job(session,job,config=config(),client=provider)
    assert provider.lookups==[order.order_number,order.order_number]
    assert job.state=='COMPLETED' and order.payment_state=='COMPLETED'
    session.close()
