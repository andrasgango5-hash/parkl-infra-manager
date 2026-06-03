"""Add device units and QR mode

Revision ID: e7c4a9d2b1f0
Revises: c4e8b1f729a0
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e7c4a9d2b1f0"
down_revision = "c4e8b1f729a0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("device", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("qr_mode", sa.String(length=20), server_default="group", nullable=False)
        )

    op.create_table(
        "device_unit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("unit_code", sa.String(length=120), nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("asset_tag", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_unit_asset_tag"), "device_unit", ["asset_tag"], unique=False)
    op.create_index(op.f("ix_device_unit_device_id"), "device_unit", ["device_id"], unique=False)
    op.create_index(
        op.f("ix_device_unit_serial_number"), "device_unit", ["serial_number"], unique=False
    )
    op.create_index(op.f("ix_device_unit_unit_code"), "device_unit", ["unit_code"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_device_unit_unit_code"), table_name="device_unit")
    op.drop_index(op.f("ix_device_unit_serial_number"), table_name="device_unit")
    op.drop_index(op.f("ix_device_unit_device_id"), table_name="device_unit")
    op.drop_index(op.f("ix_device_unit_asset_tag"), table_name="device_unit")
    op.drop_table("device_unit")

    with op.batch_alter_table("device", schema=None) as batch_op:
        batch_op.drop_column("qr_mode")
