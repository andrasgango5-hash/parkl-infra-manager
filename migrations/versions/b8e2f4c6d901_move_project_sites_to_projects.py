"""move project site data from locations to projects

Revision ID: b8e2f4c6d901
Revises: 94f3c2d8e1b0
Create Date: 2026-06-07
"""

import re
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "b8e2f4c6d901"
down_revision = "94f3c2d8e1b0"
branch_labels = None
depends_on = None


PROJECT_NOTE_PATTERN = re.compile(r"^\s*Projekt:\s*(.+?)\s*$", re.IGNORECASE)


def _active_references(connection, location_id):
    unit_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM device_unit
            WHERE location_id = :location_id AND archived_at IS NULL
            """
        ),
        {"location_id": location_id},
    ).scalar_one()
    bulk_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM bulk_stock_balance
            WHERE location_id = :location_id AND quantity > 0
            """
        ),
        {"location_id": location_id},
    ).scalar_one()
    movement_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM stock_movement
            WHERE from_location_id = :location_id OR to_location_id = :location_id
            """
        ),
        {"location_id": location_id},
    ).scalar_one()
    return unit_count, bulk_count, movement_count


def upgrade():
    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.add_column(sa.Column("site_name", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("country", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column("google_maps_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("site_notes", sa.Text(), nullable=True))

    connection = op.get_bind()
    archived_at = datetime.now(timezone.utc)
    locations = connection.execute(
        sa.text(
            """
            SELECT id, name, location_type, address, notes, archived_at
            FROM location
            WHERE location_type IN ('project_site', 'installed')
            """
        )
    ).mappings()

    for location in locations:
        unit_count, bulk_count, movement_count = _active_references(
            connection, location["id"]
        )
        if location["location_type"] == "project_site":
            match = PROJECT_NOTE_PATTERN.match(location["notes"] or "")
            project = None
            if match:
                project = connection.execute(
                    sa.text(
                        """
                        SELECT id, code, site_name, address
                        FROM project WHERE code = :code
                        """
                    ),
                    {"code": match.group(1).strip()},
                ).mappings().first()
            if project:
                connection.execute(
                    sa.text(
                        """
                        UPDATE project
                        SET site_name = CASE
                                WHEN site_name IS NULL OR site_name = '' THEN :site_name
                                ELSE site_name
                            END,
                            address = CASE
                                WHEN address IS NULL OR address = '' THEN :address
                                ELSE address
                            END
                        WHERE id = :project_id
                        """
                    ),
                    {
                        "site_name": location["name"],
                        "address": location["address"] or None,
                        "project_id": project["id"],
                    },
                )
                print(
                    "[project-site migration] "
                    f"Location #{location['id']} -> Project {project['code']}."
                )
            else:
                print(
                    "[project-site migration][MANUAL REVIEW] "
                    f"Location #{location['id']} ({location['name']!r}) could not be "
                    "matched by an exact 'Projekt: <code>' note."
                )
            if unit_count or bulk_count:
                print(
                    "[project-site migration][MANUAL REVIEW] "
                    f"Location #{location['id']} has active stock "
                    f"(units={unit_count}, bulk balances={bulk_count})."
                )
            if movement_count:
                print(
                    "[project-site migration] "
                    f"Location #{location['id']} has {movement_count} historical movements; "
                    "they remain unchanged."
                )
            connection.execute(
                sa.text(
                    """
                    UPDATE location SET archived_at = :archived_at
                    WHERE id = :location_id AND archived_at IS NULL
                    """
                ),
                {"archived_at": archived_at, "location_id": location["id"]},
            )
            continue

        if unit_count or bulk_count or movement_count:
            print(
                "[installed-location migration][MANUAL REVIEW] "
                f"Location #{location['id']} ({location['name']!r}) remains active because "
                f"units={unit_count}, bulk balances={bulk_count}, movements={movement_count}."
            )
            continue
        connection.execute(
            sa.text(
                """
                UPDATE location SET archived_at = :archived_at
                WHERE id = :location_id AND archived_at IS NULL
                """
            ),
            {"archived_at": archived_at, "location_id": location["id"]},
        )
        print(
            "[installed-location migration] "
            f"Archived unused Location #{location['id']} ({location['name']!r})."
        )


def downgrade():
    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.drop_column("site_notes")
        batch_op.drop_column("google_maps_url")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.drop_column("country")
        batch_op.drop_column("city")
        batch_op.drop_column("address")
        batch_op.drop_column("site_name")

