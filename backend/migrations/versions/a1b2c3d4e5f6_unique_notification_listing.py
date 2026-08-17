"""evita notificaciones duplicadas por preferencia y anuncio

Revision ID: a1b2c3d4e5f6
Revises: 9c4d8e7f1a2b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9c4d8e7f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Conserva la primera alerta si una instalación previa creó duplicados.
    op.execute(sa.text("""
        DELETE FROM notifications old
        USING notifications newer
        WHERE old.preference_id = newer.preference_id
          AND old.listing_id = newer.listing_id
          AND old.id > newer.id
    """))
    op.create_unique_constraint(
        "uq_notifications_preference_listing",
        "notifications",
        ["preference_id", "listing_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notifications_preference_listing", "notifications", type_="unique")
