"""Reglas económicas y Deal Score."""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("co2_max", sa.Float(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
    )
    op.create_table(
        "transport_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_country", sa.String(2), nullable=False),
        sa.Column("target_country", sa.String(2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
    )
    op.create_table(
        "repair_estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("damage_type", sa.String(40), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("min_cost", sa.Float(), nullable=False),
        sa.Column("max_cost", sa.Float(), nullable=False),
        sa.Column("expected_cost", sa.Float(), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
    )
    op.create_table(
        "deal_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_value", sa.Numeric()),
        sa.Column("purchase_cost", sa.Numeric()),
        sa.Column("import_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("repair_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("preparation_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("financing_cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("expected_profit", sa.Numeric()),
        sa.Column("roi", sa.Numeric()),
        sa.Column("score", sa.Numeric()),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("condition_bucket", sa.String(20), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("listing_id", name="uq_deal_scores_listing"),
    )
    op.create_index("ix_deal_scores_listing_id", "deal_scores", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_deal_scores_listing_id", table_name="deal_scores")
    op.drop_table("deal_scores")
    op.drop_table("repair_estimates")
    op.drop_table("transport_rates")
    op.drop_table("tax_rules")
