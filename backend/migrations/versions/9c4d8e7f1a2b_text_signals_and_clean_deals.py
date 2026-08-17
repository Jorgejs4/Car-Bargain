"""text signals and clean deal gate

Revision ID: 9c4d8e7f1a2b
Revises: 8dbcaea7206d
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "9c4d8e7f1a2b"
down_revision: Union[str, Sequence[str], None] = "8dbcaea7206d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("text_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "text_signals")
