"""Añade comentarios separados del vendedor."""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listing_snapshots", sa.Column("seller_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("listing_snapshots", "seller_comment")
