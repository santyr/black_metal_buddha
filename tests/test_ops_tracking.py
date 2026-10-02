from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.jobs import process_email_job
from app.models import Job, Order, ProductVariant, Refund, Shipment
from app.ops import build_attention_report
from app.orders import create_order
from app.reconcile import reconcile_printful_order
from app.schemas import CreateOrderIn
from app.settings import Settings
from app.shipments import upsert_printful_shipment


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


def session_and_order():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    variant = ProductVariant(
        product_slug="lotus-of-the-void",
        sku="TRACK-LOTUS-M",
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
            items=[{"sku": "TRACK-LOTUS-M", "quantity": 1}],
        ),
    )
    order.payment_state = "COMPLETED"
    order.order_state = "FULFILLMENT_SUBMITTED"
    order.paid_at = datetime.now(timezone.utc)
    session.commit()
    return session, order


def test_split_shipment_dedupes_notification_and_preserves_partial_state():
    session, order = session_and_order()
    try:
        shipment_data = {
            "id": 100,
            "status": "shipped",
            "tracking_number": "TRACK100",
            "tracking_url": "https://carrier.example/TRACK100",
            "shipped_at": "2026-09-18T12:00:00Z",
            "reshipment": False,
        }
        first = upsert_printful_shipment(
            session,
            order,
            shipment_data,
            event_type="shipment_sent",
            printful_order_status="partial",
        )
        second = upsert_printful_shipment(
            session,
            order,
            shipment_data,
            event_type="shipment_sent",
            printful_order_status="partial",
        )

        assert first.id == second.id
        assert order.order_state == "PARTIALLY_SHIPPED"
        assert order.fulfillment_state == "PARTIAL"
        assert first.tracking_number == "TRACK100"
        jobs = session.scalars(
            select(Job).where(Job.job_type.like("SEND_SHIPPING_NOTIFICATION:%"))
        ).all()
        assert len(jobs) == 1
    finally:
        session.close()


def test_fulfilled_shipment_marks_order_shipped_and_delivered_update():
    session, order = session_and_order()
    try:
        shipment = upsert_printful_shipment(
            session,
            order,
            {
                "id": 101,
                "tracking_number": "TRACK101",
                "tracking_url": "https://carrier.example/TRACK101",
                "shipped_at": "2026-09-18T12:00:00Z",
            },
            event_type="shipment_sent",
            printful_order_status="fulfilled",
        )
        assert order.order_state == "SHIPPED"
        assert order.fulfillment_state == "FULFILLED"

        delivered = upsert_printful_shipment(
            session,
            order,
            {
                "id": 101,
                "tracking_number": "TRACK101",
                "delivered_at": "2026-09-20T12:00:00Z",
            },
            event_type="shipment_delivered",
            printful_order_status="fulfilled",
        )
        assert delivered.id == shipment.id
        assert delivered.status == "DELIVERED"
        assert delivered.delivered_at is not None
    finally:
        session.close()


def test_reconciliation_repairs_missing_shipment_webhook():
    session, order = session_and_order()

    class Printful:
        def get_order_by_external_id(self, external_id):
            return {"id": 777, "external_id": external_id, "status": "partial"}

        def get_shipments(self, order_id):
            assert order_id == f"@{order.order_number}"
            return [{
                "id": 202,
                "shipment_status": "shipped",
                "tracking_number": "TRACK202",
                "tracking_url": "https://carrier.example/TRACK202",
                "shipped_at": "2026-09-18T14:00:00Z",
                "is_reshipment": False,
            }]

    try:
        result = reconcile_printful_order(session, order, client=Printful())
        assert result == "PARTIAL"
        shipment = session.scalar(
            select(Shipment).where(Shipment.printful_shipment_id == "202")
        )
        assert shipment is not None
        assert shipment.tracking_number == "TRACK202"
        assert order.order_state == "PARTIALLY_SHIPPED"
    finally:
        session.close()


def test_shipping_email_job_uses_specific_shipment():
    session, order = session_and_order()
    try:
        shipment = Shipment(
            order_id=order.id,
            printful_shipment_id="303",
            status="SHIPPED",
            tracking_number="TRACK303",
            tracking_url="https://carrier.example/TRACK303",
        )
        session.add(shipment)
        session.flush()
        job = Job(
            job_type=f"SEND_SHIPPING_NOTIFICATION:{shipment.id}",
            order_id=order.id,
            state="PENDING",
        )
        session.add(job)
        session.commit()

        class Sender:
            called = False

            def send_order_confirmation(self, received):
                raise AssertionError

            def send_shipping_notification(self, received_order, received_shipment):
                assert received_order.order_number == order.order_number
                assert received_shipment.tracking_number == "TRACK303"
                self.called = True

            def send_refund_confirmation(self, received):
                raise AssertionError

        sender = Sender()
        process_email_job(session, job, config=config(), sender=sender)
        assert sender.called is True
        assert job.state == "COMPLETED"
    finally:
        session.close()


def test_ops_report_surfaces_failures_without_pii():
    session, order = session_and_order()
    try:
        order.order_state = "FULFILLMENT_HOLD"
        failed_job = Job(
            job_type="SUBMIT_PRINTFUL_ORDER",
            order_id=order.id,
            state="FAILED",
            last_error="provider failure",
        )
        refund = Refund(
            order_id=order.id,
            square_refund_id="REF-FAIL",
            amount_cents=100,
            currency="USD",
            status="FAILED",
            reason="test",
        )
        shipment = Shipment(
            order_id=order.id,
            printful_shipment_id="404",
            status="RETURNED",
        )
        session.add_all([failed_job, refund, shipment])
        session.commit()

        report = build_attention_report(session, config=config())
        assert report["counts"]["attention_total"] >= 3
        rendered = str(report)
        assert order.order_number in rendered
        assert order.email not in rendered
        assert order.ship_address1 not in rendered
    finally:
        session.close()


def test_ops_report_flags_stale_paid_order_when_fulfillment_expected():
    session, order = session_and_order()
    try:
        order.printful_order_id = None
        order.paid_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.commit()

        report = build_attention_report(session, config=config(printful_mode="draft"))
        assert report["counts"]["stale_paid_without_printful"] == 1
    finally:
        session.close()


def test_refund_completion_cannot_be_reversed_by_late_events():
    from app.refunds import apply_refund_status
    session, order = session_and_order()
    try:
        refund = Refund(order_id=order.id, square_refund_id='late-refund', amount_cents=1000,
                        currency='USD', status='PENDING')
        session.add(refund)
        session.flush()
        for status in ['COMPLETED', 'PENDING', 'FAILED', 'COMPLETED']:
            apply_refund_status(session, refund, order, status=status)
        assert refund.status == 'COMPLETED'
        assert order.refunded_cents == 1000
        assert order.refund_state == 'PARTIAL'
    finally:
        session.close()


def test_returned_shipment_takes_precedence_over_fulfilled_order():
    session, order = session_and_order()
    try:
        upsert_printful_shipment(session, order, {'id': 901},
                                event_type='shipment_returned', printful_order_status='fulfilled')
        assert order.fulfillment_state == 'RETURNED'
    finally:
        session.close()


def test_reconciled_shipment_gets_one_notification_when_it_ships():
    session, order = session_and_order()
    try:
        for event in ['shipment_reconciled', 'shipment_sent', 'shipment_sent']:
            upsert_printful_shipment(session, order, {'id': 902}, event_type=event)
        jobs = session.scalars(select(Job).where(Job.job_type.like('SEND_SHIPPING_NOTIFICATION:%'))).all()
        assert len(jobs) == 1
    finally:
        session.close()


def test_fully_refunded_order_does_not_start_fulfillment():
    from app.jobs import process_submit_printful_job
    session, order = session_and_order()
    try:
        order.refund_state = 'COMPLETED'
        order.refunded_cents = order.total_cents
        job = Job(order_id=order.id, job_type='SUBMIT_PRINTFUL_ORDER', state='PENDING')
        session.add(job)
        session.commit()
        class NoProviderCalls:
            def get_order_by_external_id(self, _):
                raise AssertionError('A fully refunded order must not be submitted')
        process_submit_printful_job(session, job, config=config(), client=NoProviderCalls())
        assert job.state == 'CANCELED'
        assert order.printful_order_id is None
    finally:
        session.close()
