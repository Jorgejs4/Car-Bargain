"""estado por reconciliación completa y ausencias consecutivas"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a7c1d9e4b2"
down_revision: Union[str, Sequence[str], None] = "fb18ba32befd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("consecutive_misses", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("first_missed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("listings", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "last_verified_at")
    op.drop_column("listings", "first_missed_at")
    op.drop_column("listings", "consecutive_misses")
