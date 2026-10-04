"""Keep provider receipts and known fees/net separate from customer gross."""
from alembic import op
import sqlalchemy as sa

revision = "0011_paypal_receipts"
down_revision = "0010_paypal_checkout"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("paypal_capture_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("paypal_fee_cents", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("paypal_net_cents", sa.Integer(), nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text("""SELECT COUNT(*) FROM orders WHERE paypal_capture_json IS NOT NULL
        OR paypal_fee_cents IS NOT NULL OR paypal_net_cents IS NOT NULL""")).scalar():
        raise RuntimeError("PayPal receipt history must be preserved")
    with op.batch_alter_table("orders") as batch:
        for name in ("paypal_net_cents", "paypal_fee_cents", "paypal_capture_json"):
            batch.drop_column(name)
