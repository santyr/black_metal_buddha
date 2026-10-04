"""Add separate PayPal identifiers without changing existing Square columns."""
from alembic import op
import sqlalchemy as sa

revision = "0009_paypal_foundation"
down_revision = "0008_printful_catalog"
branch_labels = None
depends_on = None

ORDER_COLUMNS = (
    ("payment_provider", sa.String(32), False),
    ("paypal_order_id", sa.String(128), True),
    ("paypal_capture_id", sa.String(128), True),
    ("paypal_checkout_url", sa.String(1024), False),
    ("paypal_create_request_id", sa.String(38), True),
    ("paypal_capture_request_id", sa.String(38), True),
    ("paypal_create_requested_at", sa.DateTime(timezone=True), False),
    ("paypal_capture_requested_at", sa.DateTime(timezone=True), False),
)
REFUND_COLUMNS = (
    ("payment_provider", sa.String(32), False),
    ("paypal_refund_id", sa.String(128), True),
    ("paypal_request_id", sa.String(38), True),
    ("paypal_requested_at", sa.DateTime(timezone=True), False),
)


def upgrade() -> None:
    for table, columns in (("orders", ORDER_COLUMNS), ("refunds", REFUND_COLUMNS)):
        with op.batch_alter_table(table) as batch:
            for name, column_type, unique in columns:
                batch.add_column(sa.Column(name, column_type, nullable=True))
                if unique:
                    batch.create_unique_constraint(f"uq_{table}_{name}", [name])
    op.execute(sa.text("""UPDATE orders SET payment_provider='square'
        WHERE square_order_id IS NOT NULL OR square_payment_id IS NOT NULL
           OR square_payment_link_id IS NOT NULL OR square_checkout_url IS NOT NULL"""))
    op.execute(sa.text("""UPDATE refunds SET payment_provider='square'
        WHERE square_refund_id IS NOT NULL OR order_id IN
            (SELECT id FROM orders WHERE payment_provider='square')"""))


def downgrade() -> None:
    # Even an operation with an unknown response must retain its durable key.
    for table, columns in (("orders", ORDER_COLUMNS), ("refunds", REFUND_COLUMNS)):
        predicates = ["payment_provider='paypal'"] + [f"{name} IS NOT NULL" for name, _, _ in columns if name.startswith("paypal_")]
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE " + " OR ".join(predicates))).scalar():
            raise RuntimeError("PayPal history must be preserved; close checkout and keep this additive migration")
    for table, columns in (("refunds", REFUND_COLUMNS), ("orders", ORDER_COLUMNS)):
        with op.batch_alter_table(table) as batch:
            for name, _, unique in reversed(columns):
                if unique:
                    batch.drop_constraint(f"uq_{table}_{name}", type_="unique")
                batch.drop_column(name)
