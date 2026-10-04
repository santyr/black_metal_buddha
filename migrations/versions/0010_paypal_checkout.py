"""Retain exact checkout quotes and frozen PayPal attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0010_paypal_checkout"
down_revision = "0009_paypal_foundation"
branch_labels = None
depends_on = None

COLUMNS = (
    ("paypal_snapshot", sa.Text()),
    ("printful_estimate_json", sa.Text()),
    ("printful_estimated_at", sa.DateTime(timezone=True)),
    ("order_access_token_hash", sa.String(64)),
)


def upgrade():
    with op.batch_alter_table("orders") as batch:
        for name, kind in COLUMNS:
            batch.add_column(sa.Column(name, kind, nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text("""SELECT COUNT(*) FROM orders
        WHERE paypal_snapshot IS NOT NULL OR printful_estimate_json IS NOT NULL
           OR order_access_token_hash IS NOT NULL""")).scalar():
        raise RuntimeError("PayPal checkout history must be preserved")
    with op.batch_alter_table("orders") as batch:
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
