"""Normalize imported device categories

Revision ID: b6b4db2a2f35
Revises: 94b1120f7cfb
Create Date: 2026-05-24 00:00:00.000000

"""
from alembic import op


revision = "b6b4db2a2f35"
down_revision = "94b1120f7cfb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE device SET device_type = 'Sticker' "
        "WHERE lower(source_sheet) IN ('matricák', 'matricak')"
    )
    op.execute(
        "UPDATE device SET device_type = 'Camera' "
        "WHERE lower(source_sheet) = 'kamera'"
    )
    op.execute(
        "UPDATE device SET device_type = 'Kiosk' "
        "WHERE lower(source_sheet) = 'kioszk'"
    )
    op.execute(
        "UPDATE device SET device_type = 'Opener' "
        "WHERE lower(source_sheet) IN ('nyitó', 'nyito')"
    )
    op.execute(
        "UPDATE device SET device_type = 'Other' "
        "WHERE lower(source_sheet) IN ('egyéb', 'egyeb')"
    )


def downgrade():
    op.execute(
        "UPDATE device SET device_type = 'EV charger' "
        "WHERE lower(source_sheet) IN ('matricák', 'matricak')"
    )
    op.execute(
        "UPDATE device SET device_type = 'Sensor' "
        "WHERE lower(source_sheet) = 'kamera'"
    )
    op.execute(
        "UPDATE device SET device_type = 'Cabinet' "
        "WHERE lower(source_sheet) = 'kioszk'"
    )
    op.execute(
        "UPDATE device SET device_type = 'Network device' "
        "WHERE lower(source_sheet) IN ('nyitó', 'nyito')"
    )
