"""Normalize imported total values

Revision ID: f3a9c6d12e40
Revises: d8e4f2a91c7b
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op


revision = "f3a9c6d12e40"
down_revision = "d8e4f2a91c7b"
branch_labels = None
depends_on = None


def upgrade():
    # The real Excel workbook stores a HUF-converted unit value when a unit
    # net price is present. Device.huf_value is used as a total throughout the app.
    op.execute(
        "UPDATE device "
        "SET huf_value = huf_value * quantity "
        "WHERE source_sheet IS NOT NULL "
        "AND quantity IS NOT NULL "
        "AND quantity > 0 "
        "AND quantity <> 1 "
        "AND unit_net_price IS NOT NULL "
        "AND huf_value IS NOT NULL"
    )
    op.execute(
        "UPDATE unassigned_invoice_item "
        "SET net_amount_huf = quantity * unit_price_huf "
        "WHERE net_amount_huf IS NULL "
        "AND quantity IS NOT NULL "
        "AND unit_price_huf IS NOT NULL"
    )


def downgrade():
    op.execute(
        "UPDATE device "
        "SET huf_value = huf_value / quantity "
        "WHERE source_sheet IS NOT NULL "
        "AND quantity IS NOT NULL "
        "AND quantity > 0 "
        "AND quantity <> 1 "
        "AND unit_net_price IS NOT NULL "
        "AND huf_value IS NOT NULL"
    )
