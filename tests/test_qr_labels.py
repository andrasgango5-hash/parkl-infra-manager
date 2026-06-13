import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import create_app, db
from models import Device, DeviceUnit, Location, Project, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "qr-label-test"
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


class QrLabelTestCase(unittest.TestCase):
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
        self.project = Project(code="PRK-QR", name="QR projekt")
        self.location = Location(name="Fő raktár", location_type="warehouse")
        self.device = Device(
            asset_tag="QR-DEVICE-001",
            product_name="ABB Terra AC",
            device_type="EV charger",
            quantity=1,
            tracking_mode="unit",
            qr_mode="individual",
        )
        db.session.add_all(
            [self.user, self.project, self.location, self.device]
        )
        db.session.flush()
        self.unit = DeviceUnit(
            device_id=self.device.id,
            unit_code="ABB-001",
            asset_tag="EV-001",
            serial_number="SERIAL-001",
            status="IN_STOCK",
            location_id=self.location.id,
        )
        db.session.add(self.unit)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = self.user.id
        return client

    def test_qr_label_lists_are_distinct_and_searchable(self):
        client = self.client()
        device_page = client.get("/qr-labels/devices?q=ABB")
        unit_page = client.get("/qr-labels/units?q=SERIAL")

        self.assertEqual(device_page.status_code, 200)
        self.assertEqual(unit_page.status_code, 200)
        self.assertIn("QR-DEVICE-001", device_page.get_data(as_text=True))
        self.assertIn("EV-001", unit_page.get_data(as_text=True))
        self.assertIn("SERIAL-001", unit_page.get_data(as_text=True))

    def test_single_label_pdf_routes_return_pdf(self):
        client = self.client()
        for url in (
            f"/devices/{self.device.id}/label.pdf",
            f"/device-units/{self.unit.id}/label.pdf",
        ):
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/pdf")
            self.assertTrue(response.data.startswith(b"%PDF"))

