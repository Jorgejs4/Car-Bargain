"""Persistencia de predicciones de valoración."""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market", sa.String(length=10), nullable=False),
        sa.Column("p10", sa.Numeric(), nullable=True),
        sa.Column("p50", sa.Numeric(), nullable=True),
        sa.Column("p90", sa.Numeric(), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("condition_bucket", sa.String(length=20), nullable=False),
        sa.Column("comparables_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("listing_id", "market", name="uq_price_predictions_listing_market"),
    )
    op.create_index("ix_price_predictions_listing_id", "price_predictions", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_price_predictions_listing_id", table_name="price_predictions")
    op.drop_table("price_predictions")
