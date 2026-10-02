"""Persist the catalog managed in Printful."""

from alembic import op
import sqlalchemy as sa

revision = "0008_printful_catalog"
down_revision = "0007_refund_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("order_items") as batch:
        batch.alter_column("name_snapshot", existing_type=sa.String(200), type_=sa.String(255),
                           existing_nullable=False)
    op.add_column("product_variants", sa.Column("catalog_visible", sa.Boolean(), nullable=False,
                                               server_default=sa.false()))
    op.create_table(
        "printful_products",
        sa.Column("printful_product_id", sa.String(128), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("garment_name", sa.String(255), nullable=False),
        sa.Column("image", sa.String(255), nullable=True),
        sa.Column("source_image_url", sa.Text(), nullable=True),
        sa.Column("image_etag", sa.Text(), nullable=True),
        sa.Column("image_last_modified", sa.String(128), nullable=True),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_printful_products_slug", "printful_products", ["slug"], unique=True)
    op.create_table(
        "printful_catalog_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.String(128), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_count", sa.Integer(), nullable=False),
        sa.Column("variant_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    with op.batch_alter_table("order_items") as batch:
        batch.alter_column("name_snapshot", existing_type=sa.String(255), type_=sa.String(200),
                           existing_nullable=False)
    op.drop_table("printful_catalog_state")
    op.drop_index("ix_printful_products_slug", table_name="printful_products")
    op.drop_table("printful_products")
    op.drop_column("product_variants", "catalog_visible")
