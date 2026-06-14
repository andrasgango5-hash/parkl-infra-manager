import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import create_app, db
from models import Device, M2MSubscription, Project, UnassignedInvoiceItem, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "dashboard-operations-test"
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


class DashboardOperationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.manager = User(
            username="manager",
            password_hash=generate_password_hash("ManagerTest123!"),
            role="manager",
            is_active=True,
            force_password_change=False,
        )
        self.viewer = User(
            username="viewer",
            password_hash=generate_password_hash("ViewerTest123!"),
            role="viewer",
            is_active=True,
            force_password_change=False,
        )
        db.session.add_all(
            [
                self.manager,
                self.viewer,
                Project(code="PRK-OPS", name="Operatív projekt", status="active"),
                M2MSubscription(
                    sim_number="8944000000000000001",
                    status="active",
                    connection_type="mobile",
                    current_package="1 GB",
                ),
                Device(
                    asset_tag="OPS-001",
                    product_name="Dashboard eszköz",
                    device_type="Other",
                    quantity=1,
                    tracking_mode="bulk",
                    currency="HUF",
                    unit_net_price=1000,
                    supplier_invoice_number="INV-OPS",
                    supplier_invoice_paid=False,
                ),
                UnassignedInvoiceItem(
                    invoice_number="ORPHAN-OPS",
                    assignment_status="unassigned",
                ),
            ]
        )
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def client_for(self, user):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user.id
        return client

    def test_manager_dashboard_is_an_operational_control_center(self):
        response = self.client_for(self.manager).get("/dashboard")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for heading in (
            "Projektállapot",
            "M2M állapot",
            "Pénzügyi összesítő",
            "Legutóbbi aktivitások",
            "Gyors műveletek",
        ):
            self.assertIn(heading, page)
        self.assertIn("PRK-OPS", page)
        self.assertNotIn("Parkl munkafolyamat", page)
        self.assertNotIn("Eszköz hozzárendelése projekthez", page)

    def test_viewer_dashboard_hides_financial_summary_and_write_actions(self):
        response = self.client_for(self.viewer).get("/dashboard")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Pénzügyi összesítő", page)
        self.assertNotIn("Új projekt", page)
        self.assertIn("Eszköz keresése", page)


if __name__ == "__main__":
    unittest.main()
