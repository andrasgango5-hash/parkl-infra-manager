import unittest
from datetime import timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import (
    apply_device_state,
    create_app,
    create_movement,
    db,
    import_parsed_workbook,
    import_template_workbook,
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

    def test_released_unit_can_be_issued_to_another_project(self):
        device = Device(
            asset_tag="RELEASE-001",
            device_type="EV charger",
            product_name="Átfoglalható töltő",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="RELEASE-001-001",
            status="IN_STOCK",
            location_id=self.warehouse.id,
        )
        db.session.add_all([device, unit])
        db.session.commit()

        self.move_unit(unit, "RESERVE", project=self.project_1)
        self.move_unit(unit, "RELEASE")
        self.move_unit(unit, "ISSUE", project=self.project_2)
        self.assertEqual(unit.status, "ISSUED")
        self.assertEqual(unit.project_id, self.project_2.id)
        self.assertIsNone(unit.location_id)

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

    def test_service_from_project_clears_active_project_and_requires_new_issue(self):
        device = Device(
            asset_tag="SERVICE-PROJECT-001",
            device_type="EV charger",
            product_name="Projektből szervizbe",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="SERVICE-PROJECT-001-001",
            status="INSTALLED",
            project_id=self.project_1.id,
        )
        service = Location(name="Szerviz", location_type="service")
        db.session.add_all([device, unit, service])
        db.session.commit()

        self.move_unit(unit, "SERVICE", location=service)
        self.assertEqual(unit.status, "IN_SERVICE")
        self.assertEqual(unit.location_id, service.id)
        self.assertIsNone(unit.project_id)
        self.assertEqual(project_inventory_summary(self.project_1)["quantity"], 0)

        self.move_unit(unit, "RETURN", location=self.warehouse)
        self.assertEqual(unit.status, "RETURNED")
        self.assertIsNone(unit.project_id)
        self.move_unit(unit, "ISSUE", project=self.project_1)
        self.assertEqual(unit.status, "ISSUED")
        self.assertEqual(unit.project_id, self.project_1.id)
        self.assertIsNone(unit.location_id)

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
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 0)
        self.assertEqual(project_inventory_summary(self.project_1)["quantity"], 0)

    def test_bulk_inbound_does_not_double_initial_quantity(self):
        device = Device(
            asset_tag="INBOUND-001",
            device_type="Other",
            product_name="Bulk bevételezés",
            quantity=50,
            tracking_mode="bulk",
            location_id=self.warehouse.id,
            status="IN_STOCK",
        )
        db.session.add(device)
        db.session.flush()

        create_movement(
            device=device,
            movement_type="INBOUND",
            quantity=50,
            to_location_id=self.warehouse.id,
            user_id=self.user.id,
        )
        apply_device_state(
            device,
            "INBOUND",
            self.warehouse.id,
            quantity=50,
        )
        db.session.commit()

        self.assertEqual(
            sum(balance.quantity for balance in device.bulk_balances),
            50,
        )
        self.assertEqual(device.quantity, 50)

        create_movement(
            device=device,
            movement_type="INBOUND",
            quantity=10,
            to_location_id=self.warehouse.id,
            user_id=self.user.id,
        )
        apply_device_state(
            device,
            "INBOUND",
            self.warehouse.id,
            quantity=10,
        )
        db.session.commit()
        self.assertEqual(
            sum(balance.quantity for balance in device.bulk_balances),
            60,
        )
        self.assertEqual(device.quantity, 60)

    def test_new_bulk_device_route_creates_exact_opening_balance(self):
        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = self.user.id
            response = client.post(
                "/devices/new",
                data={
                    "asset_tag": "ROUTE-BULK",
                    "device_type": "Other",
                    "product_name": "Route bulk",
                    "inventory_kind": "bulk",
                    "initial_state": "IN_STOCK",
                    "quantity": "12",
                    "currency": "HUF",
                    "unit_net_price": "100",
                    "location_id": str(self.warehouse.id),
                },
            )
        self.assertEqual(response.status_code, 302)
        device = Device.query.filter_by(asset_tag="ROUTE-BULK").one()
        self.assertEqual(device.quantity, 12)
        self.assertEqual(sum(item.quantity for item in device.bulk_balances), 12)
        self.assertEqual(len(device.movements), 1)
        self.assertEqual(device.movements[0].movement_type, "INBOUND")

    def test_new_unit_device_route_generates_instances_and_reservation(self):
        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = self.user.id
            response = client.post(
                "/devices/new",
                data={
                    "device_type": "Router",
                    "product_name": "Teltonika RUT241",
                    "manufacturer": "Teltonika",
                    "model": "RUT241",
                    "inventory_kind": "unit",
                    "unit_code_prefix": "RUT241",
                    "initial_state": "RESERVED",
                    "initial_project_id": str(self.project_1.id),
                    "quantity": "3",
                    "location_id": str(self.warehouse.id),
                },
            )

        self.assertEqual(response.status_code, 302)
        device = Device.query.filter_by(product_name="Teltonika RUT241").one()
        self.assertEqual(device.tracking_mode, "unit")
        self.assertEqual(device.qr_mode, "individual")
        self.assertTrue(device.asset_tag)
        self.assertEqual(len(device.units), 3)
        self.assertEqual(
            [unit.unit_code for unit in device.units],
            ["RUT241-001", "RUT241-002", "RUT241-003"],
        )
        self.assertTrue(all(unit.serial_number is None for unit in device.units))
        self.assertTrue(all(unit.status == "RESERVED" for unit in device.units))
        self.assertTrue(
            all(unit.project_id == self.project_1.id for unit in device.units)
        )
        self.assertTrue(
            all(unit.location_id == self.warehouse.id for unit in device.units)
        )
        self.assertEqual(len(device.movements), 6)
        self.assertEqual(
            [movement.movement_type for movement in device.movements].count("INBOUND"),
            3,
        )
        self.assertEqual(
            [movement.movement_type for movement in device.movements].count("RESERVE"),
            3,
        )

    def test_movement_audit_filters_by_unit_project_and_type(self):
        device = Device(
            asset_tag="FILTER-UNIT",
            device_type="Router",
            product_name="Szűrhető router",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="FILTER-UNIT-001",
            status="IN_STOCK",
            location_id=self.warehouse.id,
        )
        db.session.add_all([device, unit])
        db.session.commit()
        self.move_unit(unit, "RESERVE", project=self.project_1)

        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = self.user.id
            response = client.get(
                "/movements",
                query_string={
                    "unit_id": unit.id,
                    "project_id": self.project_1.id,
                    "movement_type": "RESERVE",
                    "group_by": "project",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("FILTER-UNIT-001", body)
        self.assertIn("PRK-001 - Arena", body)
        self.assertNotIn("Nincs a szűrésnek megfelelő mozgás.", body)

    def test_manual_unit_generation_uses_explicit_location_and_movements(self):
        device = Device(
            asset_tag="GENERATE-UNIT",
            device_type="EV charger",
            product_name="Példányosítandó töltő",
            quantity=2,
            tracking_mode="unit",
            status="IN_STOCK",
            location_id=self.other_warehouse.id,
            project_id=self.project_1.id,
        )
        db.session.add(device)
        db.session.commit()

        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = self.user.id
            response = client.post(
                f"/devices/{device.id}/units/create",
                data={
                    "prefix": "GEN",
                    "start_number": "1",
                    "initial_location_id": str(self.warehouse.id),
                    "confirm": "1",
                },
            )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(device)
        units = DeviceUnit.query.filter_by(device_id=device.id).all()
        self.assertEqual(len(units), 2)
        self.assertTrue(all(unit.status == "IN_STOCK" for unit in units))
        self.assertTrue(
            all(unit.location_id == self.warehouse.id for unit in units)
        )
        self.assertTrue(all(unit.project_id is None for unit in units))
        self.assertIsNone(device.location_id)
        self.assertIsNone(device.project_id)
        self.assertEqual(len(device.movements), 2)
        self.assertTrue(
            all(movement.movement_type == "INBOUND" for movement in device.movements)
        )
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 2)
        self.assertEqual(project_inventory_summary(self.project_1)["quantity"], 0)

    def test_template_import_creates_bulk_balance_and_unit_instances(self):
        summary = {
            "projects": [],
            "locations": [],
            "devices": [
                {
                    "project_code": self.project_1.code,
                    "category": "Sticker",
                    "product_name": "Import bulk",
                    "manufacturer": "",
                    "model": "",
                    "serial_number": "",
                    "asset_tag": "IMPORT-BULK",
                    "quantity": 50,
                    "currency": "HUF",
                    "unit_net_price": 100,
                    "total_net_price": 5000,
                    "vat_rate": 27,
                    "location_name": self.warehouse.name,
                    "status": "IN_STOCK",
                    "tracking_mode": "bulk",
                    "unit_generation": False,
                    "unit_code_prefix": None,
                    "notes": "",
                },
                {
                    "project_code": self.project_1.code,
                    "category": "EV charger",
                    "product_name": "Import unit",
                    "manufacturer": "",
                    "model": "",
                    "serial_number": "",
                    "asset_tag": "IMPORT-UNIT",
                    "quantity": 3,
                    "currency": "HUF",
                    "unit_net_price": 1000,
                    "total_net_price": 3000,
                    "vat_rate": 27,
                    "location_name": self.warehouse.name,
                    "status": "RESERVED",
                    "tracking_mode": "unit",
                    "unit_generation": True,
                    "unit_code_prefix": "IU",
                    "notes": "",
                },
            ],
        }
        result = import_template_workbook(
            summary,
            Project,
            Device,
            Location,
            self.user.id,
        )
        db.session.commit()

        bulk = Device.query.filter_by(asset_tag="IMPORT-BULK").one()
        unit_device = Device.query.filter_by(asset_tag="IMPORT-UNIT").one()
        self.assertEqual(result["units_created"], 3)
        self.assertEqual(sum(item.quantity for item in bulk.bulk_balances), 50)
        self.assertEqual(len(unit_device.units), 3)
        self.assertTrue(all(unit.status == "RESERVED" for unit in unit_device.units))
        self.assertTrue(
            all(unit.project_id == self.project_1.id for unit in unit_device.units)
        )
        self.assertTrue(
            all(unit.location_id == self.warehouse.id for unit in unit_device.units)
        )
        self.assertEqual(
            project_inventory_summary(self.project_1)["quantity"],
            3,
        )

    def test_legacy_import_initial_bulk_quantity_is_not_doubled(self):
        summary = {
            "inventory_rows": [
                {
                    "source_sheet": "Matricák",
                    "source_row_number": 2,
                    "asset_tag": "LEGACY-BULK",
                    "serial_number": "",
                    "device_type": "Sticker",
                    "manufacturer": "",
                    "model": "",
                    "product_name": "Legacy matrica",
                    "subtype_note": None,
                    "supplier_manufacturer": None,
                    "version": None,
                    "quantity": 50,
                    "unit_net_price": 100,
                    "currency": "HUF",
                    "huf_value": 5000,
                    "project_code": None,
                    "notes": None,
                    "order_date": None,
                    "is_ordered": None,
                    "planned_arrival_date": None,
                    "actual_arrival_date": None,
                    "has_arrived": None,
                    "shipping_cost": None,
                    "shipping_date": None,
                    "supplier_invoice_number": None,
                    "supplier_invoice_paid": None,
                    "invoice_value": None,
                    "shipping_invoice_number": None,
                    "shipping_invoice_paid": None,
                }
            ],
            "invoice_rows": [],
        }
        result = import_parsed_workbook(summary, None, self.user.id)
        db.session.commit()
        device = Device.query.filter_by(asset_tag="LEGACY-BULK").one()
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(sum(item.quantity for item in device.bulk_balances), 50)
        self.assertEqual(device.quantity, 50)

    def test_project_summary_combines_unit_and_bulk_quantity(self):
        bulk = Device(
            asset_tag="SUMMARY-BULK",
            device_type="Sticker",
            product_name="Összesítő bulk",
            quantity=10,
            tracking_mode="bulk",
        )
        unit_device = Device(
            asset_tag="SUMMARY-UNIT",
            device_type="EV charger",
            product_name="Összesítő unit",
            quantity=2,
            tracking_mode="unit",
        )
        db.session.add_all([bulk, unit_device])
        db.session.flush()
        db.session.add(
            BulkStockBalance(
                device=bulk,
                status="ISSUED",
                quantity=7,
                project_id=self.project_1.id,
            )
        )
        db.session.add_all(
            [
                DeviceUnit(
                    device=unit_device,
                    unit_code=f"SUMMARY-{number}",
                    status="INSTALLED",
                    project_id=self.project_1.id,
                )
                for number in (1, 2)
            ]
        )
        db.session.commit()

        summary = project_inventory_summary(self.project_1)
        self.assertEqual(summary["quantity"], 9)
        self.assertEqual(summary["bulk_quantity"], 7)
        self.assertEqual(summary["unit_count"], 2)

    def test_project_can_be_created_with_site_fields(self):
        client = self.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["user_id"] = self.user.id
        response = client.post(
            "/projects/new",
            data={
                "code": "PRK-SITE",
                "name": "Helyszínes projekt",
                "customer": "Minta Kft.",
                "status": "planned",
                "site_name": "Soroksári telephely",
                "address": "Minta utca 1.",
                "city": "Budapest",
                "country": "Magyarország",
                "latitude": "47.401234",
                "longitude": "19.123456",
                "google_maps_url": "https://maps.google.com/?q=47.401234,19.123456",
                "site_notes": "Teherbejárat.",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.query.filter_by(code="PRK-SITE").one()
        self.assertEqual(project.site_name, "Soroksári telephely")
        self.assertEqual(project.city, "Budapest")
        self.assertEqual(project.latitude, Decimal("47.401234"))

    def test_project_site_location_type_cannot_be_created(self):
        client = self.app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["user_id"] = self.user.id
        response = client.post(
            "/locations/new",
            data={
                "name": "Tiltott projekt helyszín",
                "location_type": "project_site",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            Location.query.filter_by(name="Tiltott projekt helyszín").first()
        )
        self.assertIn(
            "Csak logisztikai készlethelytípus választható",
            response.get_data(as_text=True),
        )

    def test_template_project_site_fields_do_not_create_location(self):
        summary = {
            "projects": [
                {
                    "project_code": "PRK-IMPORT-SITE",
                    "project_name": "Importált helyszínes projekt",
                    "customer_name": "Import Kft.",
                    "site_name": "Import telephely",
                    "address": "Import utca 2.",
                    "city": "Győr",
                    "country": "Magyarország",
                    "latitude": Decimal("47.687456"),
                    "longitude": Decimal("17.650397"),
                    "google_maps_url": "https://maps.google.com/?q=47.687456,17.650397",
                    "site_notes": "Kapucsengő szükséges.",
                    "status": "planned",
                    "notes": "",
                }
            ],
            "locations": [],
            "devices": [],
        }
        result = import_template_workbook(
            summary, Project, Device, Location, self.user.id
        )
        db.session.commit()
        project = Project.query.filter_by(code="PRK-IMPORT-SITE").one()
        self.assertEqual(project.site_name, "Import telephely")
        self.assertEqual(project.city, "Győr")
        self.assertEqual(result["locations_created"], 0)
        self.assertIsNone(
            Location.query.filter_by(name="Import telephely").first()
        )

    def test_movement_rejects_non_logistic_target_location(self):
        legacy_site = Location(
            name="Régi projekt helyszín",
            location_type="project_site",
        )
        device = Device(
            asset_tag="LOGISTIC-ONLY",
            device_type="Sticker",
            product_name="Logisztikai teszt",
            quantity=5,
            tracking_mode="bulk",
        )
        db.session.add_all([legacy_site, device])
        db.session.commit()
        error = validate_movement(
            device,
            "INBOUND",
            to_location_id=legacy_site.id,
            quantity=5,
        )
        self.assertEqual(
            error,
            "Készletmozgás célja csak aktív logisztikai készlethely lehet.",
        )

    def test_installed_unit_stays_on_project_without_location(self):
        device = Device(
            asset_tag="INSTALL-SITE",
            device_type="EV charger",
            product_name="Telepítési hely teszt",
            quantity=1,
            tracking_mode="unit",
        )
        unit = DeviceUnit(
            device=device,
            unit_code="INSTALL-SITE-001",
            status="INSTALLED",
            project_id=self.project_1.id,
            location_id=None,
        )
        db.session.add_all([device, unit])
        db.session.commit()
        self.assertEqual(unit.project_id, self.project_1.id)
        self.assertIsNone(unit.location_id)
        self.assertEqual(project_inventory_summary(self.project_1)["installed"], 1)
        self.assertEqual(location_inventory_summary(self.warehouse)["physical"], 0)


if __name__ == "__main__":
    unittest.main()
