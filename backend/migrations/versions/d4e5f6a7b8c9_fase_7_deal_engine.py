"""Reglas económicas y Deal Score de la Fase 7."""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("tax_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("country", sa.String(2), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("co2_max", sa.Float(), nullable=False), sa.Column("rate", sa.Float(), nullable=False), sa.Column("version", sa.String(30), nullable=False))
    op.create_table("transport_rates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_country", sa.String(2), nullable=False), sa.Column("target_country", sa.String(2), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("cost", sa.Float(), nullable=False), sa.Column("version", sa.String(30), nullable=False))
    op.create_table("repair_estimates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("damage_type", sa.String(40), nullable=False), sa.Column("country", sa.String(2), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("min_cost", sa.Float(), nullable=False), sa.Column("max_cost", sa.Float(), nullable=False), sa.Column("expected_cost", sa.Float(), nullable=False), sa.Column("version", sa.String(30), nullable=False))
    op.create_table("deal_scores", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False), sa.Column("sale_value", sa.Numeric()), sa.Column("purchase_cost", sa.Numeric()), sa.Column("import_cost", sa.Numeric(), nullable=False, server_default="0"), sa.Column("repair_cost", sa.Numeric(), nullable=False, server_default="0"), sa.Column("preparation_cost", sa.Numeric(), nullable=False, server_default="0"), sa.Column("financing_cost", sa.Numeric(), nullable=False, server_default="0"), sa.Column("expected_profit", sa.Numeric()), sa.Column("roi", sa.Numeric()), sa.Column("score", sa.Numeric()), sa.Column("confidence", sa.String(20), nullable=False), sa.Column("condition_bucket", sa.String(20), nullable=False), sa.Column("model_version", sa.String(50), nullable=False), sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("listing_id", name="uq_deal_scores_listing"))
    op.create_index("ix_deal_scores_listing_id", "deal_scores", ["listing_id"])
    conn = op.get_bind()
    conn.execute(sa.text("INSERT INTO tax_rules (country,year,co2_max,rate,version) VALUES ('ES',2026,120,0.0,'ES_2026'),('ES',2026,160,0.0475,'ES_2026'),('ES',2026,200,0.0975,'ES_2026'),('ES',2026,999999,0.1475,'ES_2026')"))
    rates = {'DE':800,'FR':600,'IT':900,'NL':1000,'BE':900,'AT':1100,'LU':950,'PT':400,'ES':0}
    for country, cost in rates.items():
        conn.execute(sa.text("INSERT INTO transport_rates (source_country,target_country,year,cost,version) VALUES (:c,'ES',2026,:cost,'ES_2026')"), {'c': country, 'cost': cost})
    repairs = [('óxido',150,1200,500),('cristal roto',150,800,350),('repintado',200,1200,500),('roces',100,600,250),('abolladura',200,1500,600)]
    for damage, minimum, maximum, expected in repairs:
        conn.execute(sa.text("INSERT INTO repair_estimates (damage_type,country,year,min_cost,max_cost,expected_cost,version) VALUES (:d,'ES',2026,:mi,:ma,:e,'ES_2026')"), {'d': damage, 'mi': minimum, 'ma': maximum, 'e': expected})


def downgrade() -> None:
    op.drop_index("ix_deal_scores_listing_id", table_name="deal_scores")
    op.drop_table("deal_scores")
    op.drop_table("repair_estimates")
    op.drop_table("transport_rates")
    op.drop_table("tax_rules")
