import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import (
    apply_device_state,
    create_app,
    create_movement,
    db,
    find_or_create_bulk_balance,
    location_inventory_summary,
    project_inventory_summary,
    reverse_stock_movement,
    validate_movement,
)
from models import (
    BulkStockBalance,
    Device,
    DeviceUnit,
    Location,
    Project,
    StockMovement,
    User,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "inventory-test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = None
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15


class InventoryWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.user = User(
            username="manager",
            password_hash=generate_password_hash("ManagerTest123!"),
            role="manager",
            is_active=True,
            force_password_change=False,
        )
        self.project_1 = Project(code="PRK-001", name="Arena", status="active")
        self.project_2 = Project(code="PRK-002", name="Office", status="active")
        self.warehouse = Location(name="Fő raktár", location_type="warehouse")
        self.other_warehouse = Location(
            name="Második raktár", location_type="warehouse"
        )
        db.session.add_all(
            [
                self.user,
                self.project_1,
                self.project_2,
                self.warehouse,
                self.other_warehouse,
            ]
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def move_unit(self, unit, movement_type, project=None, location=None):
        error = validate_movement(
            unit.device,
            movement_type,
            location.id if location else None,
            project.id if project else None,
            quantity=1,
            unit=unit,
            from_location_id=unit.location_id,
        )
        self.assertIsNone(error)
        movement = create_movement(
            device=unit.device,
            unit=unit,
            movement_type=movement_type,
            quantity=1,
            from_location_id=unit.location_id,
            to_location_id=location.id if location else None,
            project_id=project.id if project else None,
            user_id=self.user.id,
        )
        apply_device_state(
            unit.device,
            movement_type,
            location.id if location else None,
            project.id if project else None,
            unit=unit,
        )
        db.session.commit()
        return movement

    def move_bulk(
        self, device, source, quantity, movement_type, project=None, location=None
    ):
        error = validate_movement(
            device,
            movement_type,
            location.id if location else None,
            project.id if project else None,
            quantity=quantity,
            source_balance=source,
            from_location_id=source.location_id if source else None,
        )
        self.assertIsNone(error)
        movement = create_movement(
            device=device,
            movement_type=movement_type,
            quantity=quantity,
            from_location_id=source.location_id if source else None,
            to_location_id=location.id if location else None,
            project_id=project.id if project else None,
            source_balance=source,
            user_id=self.user.id,
        )
        apply_device_state(
            device,
            movement_type,
            location.id if location else None,
            project.id if project else None,
            quantity=quantity,
            source_balance=source,
        )
        db.session.commit()
        return movement

    def test_unit_reservation_issue_install_return_and_views(self):
        device = Device(
            asset_tag="EV-BATCH",
            device_type="EV charger",
            product_name="Schneider EVlink Pro AC",
            quantity=3,
            tracking_mode="unit",
            qr_mode="individual",
        )
        db.session.add(device)
        db.session.flush()
        units = [
            DeviceUnit(
                device=device,
                unit_code=f"SCH-EV-{number:03d}",
                status="IN_STOCK",
                location_id=self.warehouse.id,
            )
            for number in range(1, 4)
        ]
        db.session.add_all(units)
        db.session.commit()

        unit = units[0]
        self.move_unit(unit, "RESERVE", project=self.project_1)
        self.assertEqual(project_inventory_summary(self.project_1)["quantity"], 1)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 3)
        self.assertEqual(location_inventory_summary(self.warehouse)["reserved"], 1)
        self.assertEqual(location_inventory_summary(self.warehouse)["free"], 2)

        wrong_project_error = validate_movement(
            device,
            "ISSUE",
            project_id=self.project_2.id,
            quantity=1,
            unit=unit,
            from_location_id=unit.location_id,
        )
        self.assertIn("másik projekthez", wrong_project_error)

        self.move_unit(unit, "RELEASE")
        self.assertEqual(unit.status, "IN_STOCK")
        self.assertIsNone(unit.project_id)
        self.assertEqual(location_inventory_summary(self.warehouse)["free"], 3)
        self.move_unit(unit, "RESERVE", project=self.project_1)

        self.move_unit(unit, "ISSUE", project=self.project_1)
        self.assertEqual(unit.status, "ISSUED")
        self.assertIsNone(unit.location_id)
        self.assertEqual(unit.project_id, self.project_1.id)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 2)

        self.move_unit(unit, "INSTALL", project=self.project_1)
        self.assertEqual(unit.status, "INSTALLED")
        self.assertIsNone(unit.location_id)
        self.assertEqual(project_inventory_summary(self.project_1)["installed"], 1)

        return_movement = self.move_unit(unit, "RETURN", location=self.warehouse)
        self.assertEqual(unit.status, "RETURNED")
        self.assertEqual(unit.location_id, self.warehouse.id)
        self.assertIsNone(unit.project_id)
        self.assertEqual(project_inventory_summary(self.project_1)["quantity"], 0)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 3)

        reverse_stock_movement(return_movement, self.user.id)
        db.session.commit()
        self.assertEqual(unit.status, "INSTALLED")
        self.assertIsNone(unit.location_id)
        self.assertEqual(unit.project_id, self.project_1.id)
        with self.assertRaisesRegex(ValueError, "már visszavonták"):
            reverse_stock_movement(return_movement, self.user.id)

    def test_older_unit_movement_cannot_skip_later_history(self):
        device = Device(
            asset_tag="HISTORY-001",
            device_type="EV charger",
            product_name="Történeti teszt",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="HISTORY-001-001",
            status="IN_STOCK",
            location_id=self.warehouse.id,
        )
        db.session.add_all([device, unit])
        db.session.commit()

        reserve = self.move_unit(unit, "RESERVE", project=self.project_1)
        self.move_unit(unit, "ISSUE", project=self.project_1)
        with self.assertRaisesRegex(ValueError, "legutolsó mozgása"):
            reverse_stock_movement(reserve, self.user.id)

    def test_bulk_reservation_issue_partial_return_and_reversal(self):
        device = Device(
            asset_tag="MAT-001",
            device_type="Sticker",
            product_name="Matrica",
            quantity=50,
            tracking_mode="bulk",
        )
        source = BulkStockBalance(
            device=device,
            status="IN_STOCK",
            quantity=50,
            location_id=self.warehouse.id,
        )
        db.session.add_all([device, source])
        db.session.commit()

        self.move_bulk(device, source, 20, "RESERVE", project=self.project_1)
        summary = location_inventory_summary(self.warehouse)
        self.assertEqual(summary["physical"], 50)
        self.assertEqual(summary["reserved"], 20)
        self.assertEqual(summary["free"], 30)
        self.assertEqual(project_inventory_summary(self.project_1)["reserved"], 20)

        reserved = BulkStockBalance.query.filter_by(
            device_id=device.id,
            status="RESERVED",
            project_id=self.project_1.id,
        ).one()
        wrong_project_error = validate_movement(
            device,
            "ISSUE",
            project_id=self.project_2.id,
            quantity=20,
            source_balance=reserved,
            from_location_id=reserved.location_id,
        )
        self.assertIn("másik projekthez", wrong_project_error)

        self.move_bulk(device, reserved, 5, "RELEASE")
        self.assertEqual(location_inventory_summary(self.warehouse)["reserved"], 15)
        self.assertEqual(location_inventory_summary(self.warehouse)["free"], 35)
        free_stock = BulkStockBalance.query.filter_by(
            device_id=device.id,
            status="IN_STOCK",
            location_id=self.warehouse.id,
        ).one()
        self.move_bulk(device, free_stock, 5, "RESERVE", project=self.project_1)
        self.assertEqual(location_inventory_summary(self.warehouse)["reserved"], 20)

        self.move_bulk(device, reserved, 20, "ISSUE", project=self.project_1)
        issued = BulkStockBalance.query.filter_by(
            device_id=device.id,
            status="ISSUED",
            project_id=self.project_1.id,
        ).one()
        self.assertIsNone(issued.location_id)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 30)
        self.assertEqual(project_inventory_summary(self.project_1)["issued"], 20)

        return_movement = self.move_bulk(
            device, issued, 3, "RETURN", location=self.warehouse
        )
        self.assertEqual(project_inventory_summary(self.project_1)["issued"], 17)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 33)

        reverse_stock_movement(return_movement, self.user.id)
        db.session.commit()
        self.assertEqual(project_inventory_summary(self.project_1)["issued"], 20)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 30)
        with self.assertRaisesRegex(ValueError, "már visszavonták"):
            reverse_stock_movement(return_movement, self.user.id)

    def test_service_inventory_is_physical_but_not_free(self):
        device = Device(
            asset_tag="SERVICE-001",
            device_type="Other",
            product_name="Szervizes eszköz",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="SERVICE-001-001",
            status="IN_SERVICE",
            location_id=self.warehouse.id,
        )
        db.session.add_all([device, unit])
        db.session.commit()

        summary = location_inventory_summary(self.warehouse)
        self.assertEqual(summary["physical"], 1)
        self.assertEqual(summary["service"], 1)
        self.assertEqual(summary["free"], 0)

    def test_scrapped_inventory_cannot_move(self):
        device = Device(
            asset_tag="SCRAP-001",
            device_type="Other",
            product_name="Selejtezett eszköz",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="SCRAP-001-001",
            status="SCRAPPED",
        )
        db.session.add_all([device, unit])
        db.session.commit()

        error = validate_movement(
            device,
            "INBOUND",
            to_location_id=self.warehouse.id,
            quantity=1,
            unit=unit,
        )
        self.assertEqual(error, "Selejtezett eszköz nem mozgatható tovább.")


if __name__ == "__main__":
    unittest.main()
