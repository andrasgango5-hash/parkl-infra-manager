import importlib.util
import unittest
from contextlib import contextmanager
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "b8e2f4c6d901_move_project_sites_to_projects.py"
)


class FakeBatch:
    def add_column(self, column):
        pass


class FakeOp:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def batch_alter_table(self, *args, **kwargs):
        yield FakeBatch()

    def get_bind(self):
        return self.connection


class ProjectLocationMigrationTestCase(unittest.TestCase):
    def test_exact_project_note_moves_site_data_and_archives_location(self):
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    CREATE TABLE project (
                        id INTEGER PRIMARY KEY,
                        code VARCHAR(60),
                        site_name VARCHAR(160),
                        address VARCHAR(255)
                    )
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    CREATE TABLE location (
                        id INTEGER PRIMARY KEY,
                        name VARCHAR(160),
                        location_type VARCHAR(40),
                        address VARCHAR(255),
                        notes TEXT,
                        archived_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    CREATE TABLE device_unit (
                        id INTEGER PRIMARY KEY,
                        location_id INTEGER,
                        archived_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    CREATE TABLE bulk_stock_balance (
                        id INTEGER PRIMARY KEY,
                        location_id INTEGER,
                        quantity FLOAT
                    )
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    CREATE TABLE stock_movement (
                        id INTEGER PRIMARY KEY,
                        from_location_id INTEGER,
                        to_location_id INTEGER
                    )
                    """
                )
            )
            connection.execute(
                sa.text("INSERT INTO project (id, code) VALUES (1, 'PRK-001')")
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO location
                        (id, name, location_type, address, notes, archived_at)
                    VALUES
                        (10, 'Arena helyszín', 'project_site',
                         'Stefánia út 2.', 'Projekt: PRK-001', NULL)
                    """
                )
            )

            spec = importlib.util.spec_from_file_location(
                "project_location_migration", MIGRATION_PATH
            )
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            migration.op = FakeOp(connection)
            migration.upgrade()

            project = connection.execute(
                sa.text(
                    "SELECT site_name, address FROM project WHERE id = 1"
                )
            ).mappings().one()
            location = connection.execute(
                sa.text("SELECT archived_at FROM location WHERE id = 10")
            ).mappings().one()

            self.assertEqual(project["site_name"], "Arena helyszín")
            self.assertEqual(project["address"], "Stefánia út 2.")
            self.assertIsNotNone(location["archived_at"])


if __name__ == "__main__":
    unittest.main()

