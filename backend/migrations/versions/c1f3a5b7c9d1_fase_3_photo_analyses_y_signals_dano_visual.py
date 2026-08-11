"""fase 3: photo_analyses y señales de daño visual en listings

Revision ID: c1f3a5b7c9d1
Revises: bcc8865e2d0a
Create Date: 2026-08-11 17:20:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1f3a5b7c9d1'
down_revision: str | Sequence[str] | None = 'bcc8865e2d0a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('listings', sa.Column('photo_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('listings', sa.Column('needs_review', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('listings', sa.Column('risk_score', sa.Numeric(precision=4, scale=3), nullable=True))
    op.create_table('photo_analyses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_id', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.Text(), nullable=False),
    sa.Column('local_path', sa.Text(), nullable=True),
    sa.Column('label', sa.String(length=50), nullable=True),
    sa.Column('probability', sa.Numeric(precision=5, scale=4), nullable=True),
    sa.Column('model_version', sa.String(length=100), nullable=True),
    sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('listing_id', 'image_url', name='uq_photo_analyses_listing_image')
    )
    op.create_index(op.f('ix_photo_analyses_listing_id'), 'photo_analyses', ['listing_id'], unique=False)
    op.create_index(op.f('ix_photo_analyses_analyzed_at'), 'photo_analyses', ['analyzed_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_photo_analyses_analyzed_at'), table_name='photo_analyses')
    op.drop_index(op.f('ix_photo_analyses_listing_id'), table_name='photo_analyses')
    op.drop_table('photo_analyses')
    op.drop_column('listings', 'risk_score')
    op.drop_column('listings', 'needs_review')
    op.drop_column('listings', 'photo_signals')
