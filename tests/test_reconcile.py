import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Job, ProductVariant
from app.orders import create_order
from app.reconcile import ReconciliationError, reconcile_printful_order, reconcile_square_order
from app.schemas import CreateOrderIn


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session


def create_test_order(session):
    variant = ProductVariant(
        product_slug="lotus-of-the-void",
        sku="TEST-LOTUS-M",
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

    return create_order(
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
            items=[{"sku": "TEST-LOTUS-M", "quantity": 1}],
        ),
    )


class SquarePaid:
    order_number = ""

    def get_order(self, order_id):
        return {
            "id": order_id,
            "reference_id": self.order_number,
            "line_items": [{
                "name": "Lotus of the Void",
                "quantity": "1",
                "base_price_money": {"amount": 3200, "currency": "USD"},
            }],
            "total_service_charge_money": {"amount": 0, "currency": "USD"},
            "total_discount_money": {"amount": 0, "currency": "USD"},
            "total_tax_money": {"amount": 0, "currency": "USD"},
            "total_money": {"amount": 3200, "currency": "USD"},
            "tenders": [{"payment_id": "PAY123"}],
        }

    def get_payment(self, payment_id):
        return {
            "id": payment_id,
            "order_id": "SQORDER",
            "status": "COMPLETED",
            "amount_money": {"amount": 3200, "currency": "USD"},
        }

    @staticmethod
    def payment_id_from_order(order):
        return order["tenders"][0]["payment_id"]


class SquareWrongAmount(SquarePaid):
    def get_payment(self, payment_id):
        payment = super().get_payment(payment_id)
        payment["amount_money"]["amount"] = 1
        return payment


class PrintfulDraft:
    def get_order_by_external_id(self, external_id):
        return {"id": 777, "external_id": external_id, "status": "draft"}

    def get_shipments(self, order_id):
        return []


def test_square_reconciliation_repairs_missed_webhook(session):
    order = create_test_order(session)
    order.square_order_id = "SQORDER"
    session.commit()

    client = SquarePaid()
    client.order_number = order.order_number
    result = reconcile_square_order(session, order, client=client)
    assert result == "PAID"
    assert order.payment_state == "COMPLETED"
    assert order.square_payment_id == "PAY123"
    assert len(session.scalars(select(Job)).all()) == 2


def test_square_reconciliation_rejects_amount_mismatch(session):
    order = create_test_order(session)
    order.square_order_id = "SQORDER"
    session.commit()

    client = SquareWrongAmount()
    client.order_number = order.order_number
    with pytest.raises(ReconciliationError):
        reconcile_square_order(session, order, client=client)
    assert order.payment_state != "COMPLETED"


def test_printful_reconciliation_uses_external_id(session):
    order = create_test_order(session)
    order.payment_state = "COMPLETED"
    order.order_state = "PAID"
    session.commit()

    result = reconcile_printful_order(session, order, client=PrintfulDraft())
    assert result == "DRAFT"
    assert order.printful_order_id == "777"
    assert order.fulfillment_state == "DRAFT"
    assert order.order_state == "FULFILLMENT_SUBMITTED"


def test_late_failed_payment_does_not_undo_completed_payment(session):
    order = create_test_order(session)
    order.square_order_id = 'SQORDER'
    order.square_payment_id = 'PAY123'
    order.payment_state = 'COMPLETED'
    order.order_state = 'IN_PRODUCTION'
    session.commit()

    class LateFailure(SquarePaid):
        def get_payment(self, payment_id):
            payment = super().get_payment(payment_id)
            payment['status'] = 'FAILED'
            return payment

    client = LateFailure()
    client.order_number = order.order_number
    reconcile_square_order(session, order, client=client)
    assert order.payment_state == 'COMPLETED'
    assert order.order_state == 'IN_PRODUCTION'
