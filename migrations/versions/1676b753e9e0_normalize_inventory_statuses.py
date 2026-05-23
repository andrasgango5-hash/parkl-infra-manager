"""Normalize inventory statuses

Revision ID: 1676b753e9e0
Revises: 0c68b5e90afe
Create Date: 2026-05-23 23:22:51.121598

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1676b753e9e0"
down_revision = "0c68b5e90afe"
branch_labels = None
depends_on = None


def upgrade():
    status_map = {
        "in_stock": "IN_STOCK",
        "unassigned": "IN_STOCK",
        "in_transit": "ISSUED",
        "installed": "INSTALLED",
        "retired": "SCRAPPED",
    }
    movement_map = {
        "created": "INBOUND",
        "received": "INBOUND",
        "transfer": "TRANSFER",
        "installed": "INSTALL",
        "returned": "RETURN",
        "maintenance": "SERVICE",
        "retired": "SCRAP",
    }
    for old_status, new_status in status_map.items():
        op.execute(
            f"UPDATE device SET status = '{new_status}' WHERE status = '{old_status}'"
        )
    for old_type, new_type in movement_map.items():
        op.execute(
            "UPDATE stock_movement "
            f"SET movement_type = '{new_type}' WHERE movement_type = '{old_type}'"
        )


def downgrade():
    status_map = {
        "IN_STOCK": "in_stock",
        "ISSUED": "in_transit",
        "INSTALLED": "installed",
        "SCRAPPED": "retired",
    }
    movement_map = {
        "INBOUND": "received",
        "TRANSFER": "transfer",
        "INSTALL": "installed",
        "RETURN": "returned",
        "SERVICE": "maintenance",
        "SCRAP": "retired",
    }
    for new_status, old_status in status_map.items():
        op.execute(
            f"UPDATE device SET status = '{old_status}' WHERE status = '{new_status}'"
        )
    for new_type, old_type in movement_map.items():
        op.execute(
            "UPDATE stock_movement "
            f"SET movement_type = '{old_type}' WHERE movement_type = '{new_type}'"
        )
