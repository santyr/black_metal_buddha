"""Persist refund requests before contacting Square."""

from alembic import op
import sqlalchemy as sa

revision = "0007_refund_requests"
down_revision = "0006_canary_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("refunds") as batch:
        batch.alter_column("square_refund_id", existing_type=sa.String(128),
                           type_=sa.String(255), existing_nullable=False, nullable=True)
        batch.add_column(sa.Column("idempotency_key", sa.String(45), nullable=True))
        batch.create_unique_constraint("uq_refunds_idempotency_key", ["idempotency_key"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM refunds WHERE square_refund_id IS NULL")).scalar():
        raise RuntimeError("Resolve outstanding refund requests before downgrading")
    with op.batch_alter_table("refunds") as batch:
        batch.drop_constraint("uq_refunds_idempotency_key", type_="unique")
        batch.drop_column("idempotency_key")
        batch.alter_column("square_refund_id", existing_type=sa.String(255),
                           type_=sa.String(128), existing_nullable=True, nullable=False)
