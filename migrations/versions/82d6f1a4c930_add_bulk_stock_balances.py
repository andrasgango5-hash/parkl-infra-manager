"""add bulk stock balances

Revision ID: 82d6f1a4c930
Revises: 7c1d4e8f2a90
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "82d6f1a4c930"
down_revision = "7c1d4e8f2a90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bulk_stock_balance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_bulk_stock_balance_quantity",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bulk_stock_balance_device_id",
        "bulk_stock_balance",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_bulk_stock_balance_status",
        "bulk_stock_balance",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_bulk_stock_balance_location_id",
        "bulk_stock_balance",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        "ix_bulk_stock_balance_project_id",
        "bulk_stock_balance",
        ["project_id"],
        unique=False,
    )

    with op.batch_alter_table("stock_movement") as batch_op:
        batch_op.add_column(sa.Column("from_status", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("to_status", sa.String(length=40), nullable=True))

    op.execute(
        """
        UPDATE stock_movement
        SET to_status = CASE movement_type
            WHEN 'INBOUND' THEN 'IN_STOCK'
            WHEN 'RESERVE' THEN 'RESERVED'
            WHEN 'ISSUE' THEN 'ISSUED'
            WHEN 'INSTALL' THEN 'INSTALLED'
            WHEN 'RETURN' THEN 'RETURNED'
            WHEN 'SERVICE' THEN 'IN_SERVICE'
            WHEN 'SCRAP' THEN 'SCRAPPED'
            ELSE NULL
        END
        WHERE to_status IS NULL
        """
    )

    # Preserve every existing bulk Device as one opening balance. Existing
    # StockMovement rows remain immutable historical records.
    op.execute(
        """
        INSERT INTO bulk_stock_balance (
            device_id, status, quantity, location_id, project_id, created_at, updated_at
        )
        SELECT
            id,
            status,
            CASE WHEN quantity IS NULL OR quantity < 0 THEN 0 ELSE quantity END,
            location_id,
            project_id,
            created_at,
            updated_at
        FROM device
        WHERE tracking_mode = 'bulk'
        """
    )


def downgrade():
    with op.batch_alter_table("stock_movement") as batch_op:
        batch_op.drop_column("to_status")
        batch_op.drop_column("from_status")

    op.drop_index(
        "ix_bulk_stock_balance_project_id",
        table_name="bulk_stock_balance",
    )
    op.drop_index(
        "ix_bulk_stock_balance_location_id",
        table_name="bulk_stock_balance",
    )
    op.drop_index(
        "ix_bulk_stock_balance_status",
        table_name="bulk_stock_balance",
    )
    op.drop_index(
        "ix_bulk_stock_balance_device_id",
        table_name="bulk_stock_balance",
    )
    op.drop_table("bulk_stock_balance")
