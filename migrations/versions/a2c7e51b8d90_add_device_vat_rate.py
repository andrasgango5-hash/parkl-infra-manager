"""Add device VAT rate

Revision ID: a2c7e51b8d90
Revises: f3a9c6d12e40
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a2c7e51b8d90"
down_revision = "f3a9c6d12e40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("device", sa.Column("vat_rate", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("device", "vat_rate")
