"""Favoritos y búsquedas guardadas.

Revision ID: a7c9e1f2b3d4
Revises: fb18ba32befd
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a7c9e1f2b3d4"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorite_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=64), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_key", "listing_id", name="uq_favorite_listings_user_listing"),
    )
    op.create_index("ix_favorite_listings_user_key", "favorite_listings", ["user_key"])
    op.create_index("ix_favorite_listings_listing_id", "favorite_listings", ["listing_id"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_saved_searches_user_key", "saved_searches", ["user_key"])


def downgrade() -> None:
    op.drop_index("ix_saved_searches_user_key", table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_index("ix_favorite_listings_listing_id", table_name="favorite_listings")
    op.drop_index("ix_favorite_listings_user_key", table_name="favorite_listings")
    op.drop_table("favorite_listings")
