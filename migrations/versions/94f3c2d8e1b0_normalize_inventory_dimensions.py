"""normalize inventory location and project dimensions

Revision ID: 94f3c2d8e1b0
Revises: 82d6f1a4c930
Create Date: 2026-06-06
"""

from alembic import op


revision = "94f3c2d8e1b0"
down_revision = "82d6f1a4c930"
branch_labels = None
depends_on = None


def upgrade():
    # Issued/installed/scrapped inventory is no longer physically present at
    # an inventory location. Historical source/target data remains in
    # stock_movement.
    op.execute(
        """
        UPDATE device_unit
        SET location_id = NULL
        WHERE status IN ('ISSUED', 'INSTALLED', 'SCRAPPED')
        """
    )
    op.execute(
        """
        UPDATE bulk_stock_balance
        SET location_id = NULL
        WHERE status IN ('ISSUED', 'INSTALLED', 'SCRAPPED')
        """
    )

    # Warehouse/returned/service/scrapped inventory has no active project.
    # Previous project assignment remains available in movement history.
    op.execute(
        """
        UPDATE device_unit
        SET project_id = NULL
        WHERE status IN ('IN_STOCK', 'RETURNED', 'IN_SERVICE', 'SCRAPPED')
        """
    )
    op.execute(
        """
        UPDATE bulk_stock_balance
        SET project_id = NULL
        WHERE status IN ('IN_STOCK', 'RETURNED', 'IN_SERVICE', 'SCRAPPED')
        """
    )

    # The legacy Device dimensions are mirrors only. Unit-tracked product
    # masters must not look like active physical inventory.
    op.execute(
        """
        UPDATE device
        SET location_id = NULL,
            project_id = NULL
        WHERE tracking_mode = 'unit'
        """
    )
    op.execute(
        """
        UPDATE stock_movement
        SET to_location_id = NULL
        WHERE movement_type IN ('ISSUE', 'INSTALL', 'SCRAP')
        """
    )
    op.execute(
        """
        UPDATE stock_movement
        SET from_project_id = COALESCE(from_project_id, project_id)
        WHERE movement_type IN ('RETURN', 'SERVICE', 'SCRAP')
          AND project_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE stock_movement
        SET to_project_id = NULL,
            project_id = NULL
        WHERE movement_type IN ('INBOUND', 'RETURN', 'SERVICE', 'SCRAP', 'RELEASE')
        """
    )


def downgrade():
    # The removed active dimensions cannot be reconstructed reliably. The
    # immutable movement history still contains the original locations and
    # projects, so downgrade intentionally performs no lossy guesswork.
    pass
