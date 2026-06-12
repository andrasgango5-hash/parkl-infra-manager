"""add M2M subscription module

Revision ID: d4a7c2e19b60
Revises: c9f3a5d7e102
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op


revision = "d4a7c2e19b60"
down_revision = "c9f3a5d7e102"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "m2m_subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscriber_name", sa.String(length=160), nullable=True),
        sa.Column("account_number", sa.String(length=100), nullable=True),
        sa.Column("contract_number", sa.String(length=100), nullable=True),
        sa.Column("registration_date", sa.Date(), nullable=True),
        sa.Column("phone_number", sa.String(length=80), nullable=True),
        sa.Column("device_number", sa.String(length=100), nullable=True),
        sa.Column("location_name", sa.String(length=160), nullable=True),
        sa.Column("device_identifier", sa.String(length=160), nullable=True),
        sa.Column("sim_number", sa.String(length=120), nullable=True),
        sa.Column("tariff_name", sa.String(length=160), nullable=True),
        sa.Column("current_package", sa.String(length=160), nullable=True),
        sa.Column("current_monthly_fee", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("teltonika_device_id", sa.Integer(), nullable=True),
        sa.Column("last_api_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'inactive', 'cancelled')",
            name="ck_m2m_subscription_status",
        ),
        sa.ForeignKeyConstraint(
            ["teltonika_device_id"],
            ["device.id"],
            name="fk_m2m_subscription_teltonika_device_id_device",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "subscriber_name",
        "account_number",
        "contract_number",
        "phone_number",
        "device_number",
        "location_name",
        "device_identifier",
        "sim_number",
        "tariff_name",
        "current_package",
        "status",
        "teltonika_device_id",
    ):
        op.create_index(
            op.f(f"ix_m2m_subscription_{column}"),
            "m2m_subscription",
            [column],
            unique=False,
        )

    op.create_table(
        "m2m_monthly_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("usage_mb", sa.Numeric(14, 2), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "month >= 1 AND month <= 12", name="ck_m2m_usage_month"
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'import', 'teltonika_api')",
            name="ck_m2m_usage_source",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["m2m_subscription.id"],
            name="fk_m2m_monthly_usage_subscription_id_m2m_subscription",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "year",
            "month",
            "source",
            name="uq_m2m_usage_subscription_month_source",
        ),
    )
    for column in ("subscription_id", "year", "month", "source"):
        op.create_index(
            op.f(f"ix_m2m_monthly_usage_{column}"),
            "m2m_monthly_usage",
            [column],
            unique=False,
        )

    op.create_table(
        "m2m_package_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(length=160), nullable=False),
        sa.Column("monthly_fee", sa.Numeric(14, 2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["m2m_subscription.id"],
            name="fk_m2m_package_history_subscription_id_m2m_subscription",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_m2m_package_history_subscription_id"),
        "m2m_package_history",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_m2m_package_history_valid_from"),
        "m2m_package_history",
        ["valid_from"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_m2m_package_history_valid_from"),
        table_name="m2m_package_history",
    )
    op.drop_index(
        op.f("ix_m2m_package_history_subscription_id"),
        table_name="m2m_package_history",
    )
    op.drop_table("m2m_package_history")

    for column in ("source", "month", "year", "subscription_id"):
        op.drop_index(
            op.f(f"ix_m2m_monthly_usage_{column}"),
            table_name="m2m_monthly_usage",
        )
    op.drop_table("m2m_monthly_usage")

    for column in (
        "teltonika_device_id",
        "status",
        "current_package",
        "tariff_name",
        "sim_number",
        "device_identifier",
        "location_name",
        "device_number",
        "phone_number",
        "contract_number",
        "account_number",
        "subscriber_name",
    ):
        op.drop_index(
            op.f(f"ix_m2m_subscription_{column}"),
            table_name="m2m_subscription",
        )
    op.drop_table("m2m_subscription")
