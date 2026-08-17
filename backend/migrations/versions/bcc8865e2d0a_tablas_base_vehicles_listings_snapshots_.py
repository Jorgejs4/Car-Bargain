"""tablas base: vehicles, listings, snapshots, eventos

Revision ID: bcc8865e2d0a
Revises:
Create Date: 2026-08-11 15:49:57.098493

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bcc8865e2d0a'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('vehicles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('brand', sa.String(length=100), nullable=False),
    sa.Column('model', sa.String(length=150), nullable=True),
    sa.Column('generation', sa.String(length=100), nullable=True),
    sa.Column('variant', sa.String(length=150), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('registration_date', sa.Date(), nullable=True),
    sa.Column('fuel', sa.String(length=50), nullable=True),
    sa.Column('transmission', sa.String(length=50), nullable=True),
    sa.Column('drivetrain', sa.String(length=50), nullable=True),
    sa.Column('power_kw', sa.Numeric(), nullable=True),
    sa.Column('engine_cc', sa.Integer(), nullable=True),
    sa.Column('co2_g_km', sa.Numeric(), nullable=True),
    sa.Column('body_type', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('listings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('source_listing_id', sa.String(length=255), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('seller_type', sa.String(length=30), nullable=True),
    sa.Column('country', sa.String(length=2), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('ACTIVE', 'STALE', 'REMOVED', 'SOLD', name='listingstatus', native_enum=False, create_constraint=True, length=30), server_default='ACTIVE', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'source_listing_id', name='uq_listings_source_listing_id')
    )
    op.create_index(op.f('ix_listings_status'), 'listings', ['status'], unique=False)
    op.create_index(op.f('ix_listings_vehicle_id'), 'listings', ['vehicle_id'], unique=False)
    op.create_table('listing_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.Enum('LISTED', 'PRICE_CHANGED', 'DESCRIPTION_CHANGED', 'MILEAGE_CHANGED', 'STATUS_CHANGED', 'REMOVED', 'REAPPEARED', name='listingeventtype', native_enum=False, create_constraint=True, length=40), nullable=False),
    sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listing_events_event_timestamp'), 'listing_events', ['event_timestamp'], unique=False)
    op.create_index(op.f('ix_listing_events_listing_id'), 'listing_events', ['listing_id'], unique=False)
    op.create_table('listing_snapshots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('listing_id', sa.Integer(), nullable=False),
    sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('mileage', sa.Integer(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('seller_type', sa.String(length=30), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('condition_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listing_snapshots_listing_id'), 'listing_snapshots', ['listing_id'], unique=False)
    op.create_index(op.f('ix_listing_snapshots_scraped_at'), 'listing_snapshots', ['scraped_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_listing_snapshots_scraped_at'), table_name='listing_snapshots')
    op.drop_index(op.f('ix_listing_snapshots_listing_id'), table_name='listing_snapshots')
    op.drop_table('listing_snapshots')
    op.drop_index(op.f('ix_listing_events_listing_id'), table_name='listing_events')
    op.drop_index(op.f('ix_listing_events_event_timestamp'), table_name='listing_events')
    op.drop_table('listing_events')
    op.drop_index(op.f('ix_listings_vehicle_id'), table_name='listings')
    op.drop_index(op.f('ix_listings_status'), table_name='listings')
    op.drop_table('listings')
    op.drop_table('vehicles')
