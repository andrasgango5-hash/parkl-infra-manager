"""add bulk and unit inventory tracking

Revision ID: 7c1d4e8f2a90
Revises: 58b6a1c2d3e4
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "7c1d4e8f2a90"
down_revision = "58b6a1c2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("device") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tracking_mode",
                sa.String(length=20),
                nullable=False,
                server_default="bulk",
            )
        )
        batch_op.create_index("ix_device_tracking_mode", ["tracking_mode"], unique=False)
        batch_op.create_check_constraint(
            "ck_device_tracking_mode",
            "tracking_mode IN ('bulk', 'unit')",
        )

    with op.batch_alter_table("device_unit") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=40),
                nullable=False,
                server_default="IN_STOCK",
            )
        )
        batch_op.add_column(sa.Column("location_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_device_unit_location_id_location", "location", ["location_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_device_unit_project_id_project", "project", ["project_id"], ["id"]
        )
        batch_op.create_index("ix_device_unit_status", ["status"], unique=False)
        batch_op.create_index("ix_device_unit_location_id", ["location_id"], unique=False)
        batch_op.create_index("ix_device_unit_project_id", ["project_id"], unique=False)

    with op.batch_alter_table("stock_movement") as batch_op:
        batch_op.add_column(sa.Column("quantity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("unit_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("from_project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("to_project_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("reversal_of_movement_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_stock_movement_unit_id_device_unit",
            "device_unit",
            ["unit_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_stock_movement_from_project_id_project",
            "project",
            ["from_project_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_stock_movement_to_project_id_project",
            "project",
            ["to_project_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_stock_movement_reversal_id_stock_movement",
            "stock_movement",
            ["reversal_of_movement_id"],
            ["id"],
        )
        batch_op.create_index("ix_stock_movement_unit_id", ["unit_id"], unique=False)
        batch_op.create_index(
            "ix_stock_movement_reversal_of_movement_id",
            ["reversal_of_movement_id"],
            unique=False,
        )
        batch_op.create_check_constraint(
            "ck_stock_movement_quantity_positive",
            "quantity IS NULL OR quantity > 0",
        )
        batch_op.create_check_constraint(
            "ck_stock_movement_unit_quantity",
            "unit_id IS NULL OR quantity = 1",
        )
        batch_op.create_check_constraint(
            "ck_stock_movement_not_self_reversal",
            "reversal_of_movement_id IS NULL OR reversal_of_movement_id != id",
        )

    # Existing rows stay backward compatible. Devices that already have units
    # become unit-tracked, and unit state starts from the former parent state.
    op.execute(
        """
        UPDATE device
        SET tracking_mode = 'unit'
        WHERE EXISTS (
            SELECT 1 FROM device_unit
            WHERE device_unit.device_id = device.id
              AND device_unit.archived_at IS NULL
        )
        """
    )
    op.execute(
        """
        UPDATE device_unit
        SET status = (
                SELECT device.status FROM device WHERE device.id = device_unit.device_id
            ),
            location_id = (
                SELECT device.location_id FROM device WHERE device.id = device_unit.device_id
            ),
            project_id = (
                SELECT device.project_id FROM device WHERE device.id = device_unit.device_id
            )
        """
    )
    op.execute(
        """
        UPDATE stock_movement
        SET to_project_id = project_id
        WHERE project_id IS NOT NULL
          AND to_project_id IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("stock_movement") as batch_op:
        batch_op.drop_constraint(
            "ck_stock_movement_not_self_reversal", type_="check"
        )
        batch_op.drop_constraint(
            "ck_stock_movement_unit_quantity", type_="check"
        )
        batch_op.drop_constraint(
            "ck_stock_movement_quantity_positive", type_="check"
        )
        batch_op.drop_index("ix_stock_movement_reversal_of_movement_id")
        batch_op.drop_index("ix_stock_movement_unit_id")
        batch_op.drop_constraint(
            "fk_stock_movement_reversal_id_stock_movement", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_stock_movement_to_project_id_project", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_stock_movement_from_project_id_project", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_stock_movement_unit_id_device_unit", type_="foreignkey"
        )
        batch_op.drop_column("reversal_of_movement_id")
        batch_op.drop_column("to_project_id")
        batch_op.drop_column("from_project_id")
        batch_op.drop_column("unit_id")
        batch_op.drop_column("quantity")

    with op.batch_alter_table("device_unit") as batch_op:
        batch_op.drop_index("ix_device_unit_project_id")
        batch_op.drop_index("ix_device_unit_location_id")
        batch_op.drop_index("ix_device_unit_status")
        batch_op.drop_constraint("fk_device_unit_project_id_project", type_="foreignkey")
        batch_op.drop_constraint("fk_device_unit_location_id_location", type_="foreignkey")
        batch_op.drop_column("project_id")
        batch_op.drop_column("location_id")
        batch_op.drop_column("status")

    with op.batch_alter_table("device") as batch_op:
        batch_op.drop_constraint("ck_device_tracking_mode", type_="check")
        batch_op.drop_index("ix_device_tracking_mode")
        batch_op.drop_column("tracking_mode")
