"""add Teltonika RMS fields

Revision ID: e6b9f4a21d30
Revises: d4a7c2e19b60
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op


revision = "e6b9f4a21d30"
down_revision = "d4a7c2e19b60"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("m2m_subscription", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("teltonika_rms_device_id", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("teltonika_rms_name", sa.String(length=160), nullable=True)
        )
        batch_op.add_column(
            sa.Column("teltonika_imei", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("teltonika_operator", sa.String(length=160), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "connection_type",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(
            sa.Column("last_rms_sync_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("last_rms_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("rms_sent_raw", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("rms_received_raw", sa.String(length=120), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_m2m_subscription_teltonika_rms_device_id"),
            ["teltonika_rms_device_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_m2m_subscription_teltonika_imei"),
            ["teltonika_imei"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_m2m_subscription_connection_type"),
            ["connection_type"],
            unique=False,
        )
        batch_op.create_check_constraint(
            "ck_m2m_subscription_connection_type",
            "connection_type IN ('mobile', 'wired', 'unknown')",
        )


def downgrade():
    with op.batch_alter_table("m2m_subscription", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_m2m_subscription_connection_type",
            type_="check",
        )
        batch_op.drop_index(
            batch_op.f("ix_m2m_subscription_connection_type")
        )
        batch_op.drop_index(batch_op.f("ix_m2m_subscription_teltonika_imei"))
        batch_op.drop_index(
            batch_op.f("ix_m2m_subscription_teltonika_rms_device_id")
        )
        batch_op.drop_column("rms_received_raw")
        batch_op.drop_column("rms_sent_raw")
        batch_op.drop_column("last_rms_error")
        batch_op.drop_column("last_rms_sync_at")
        batch_op.drop_column("connection_type")
        batch_op.drop_column("teltonika_operator")
        batch_op.drop_column("teltonika_imei")
        batch_op.drop_column("teltonika_rms_name")
        batch_op.drop_column("teltonika_rms_device_id")
