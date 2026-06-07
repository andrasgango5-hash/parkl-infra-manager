import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import create_app, db
from models import (
    Device,
    Project,
    StockMovement,
    UnassignedInvoiceItem,
    User,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "finance-test"
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


class FinanceWorkflowTestCase(unittest.TestCase):
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
        self.technician = User(
            username="technician",
            password_hash=generate_password_hash("TechnicianTest123!"),
            role="technician",
            is_active=True,
            force_password_change=False,
        )
        self.admin = User(
            username="admin",
            password_hash=generate_password_hash("AdminTest123!"),
            role="admin",
            is_admin=True,
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
        self.project = Project(code="PRK-FIN", name="Pénzügyi projekt")
        self.device = Device(
            asset_tag="FIN-001",
            product_name="Pénzügyi teszteszköz",
            device_type="Other",
            quantity=2,
            currency="HUF",
            unit_net_price=1000,
        )
        self.item = UnassignedInvoiceItem(
            invoice_number="INV-001",
            partner="Teszt Partner",
            description="Tisztázandó sor",
            quantity=2,
            unit_price_huf=1000,
            assignment_status="unassigned",
        )
        db.session.add_all(
            [
                self.manager,
                self.technician,
                self.admin,
                self.viewer,
                self.project,
                self.device,
                self.item,
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

    def test_finance_pages_are_visible_to_admin_and_manager_only(self):
        self.assertEqual(self.client_for(self.admin).get("/finance").status_code, 200)
        self.assertEqual(self.client_for(self.manager).get("/finance").status_code, 200)
        for user in (self.technician, self.viewer):
            response = self.client_for(user).get("/finance")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/dashboard")

    def test_invoice_clarification_does_not_create_stock_movement(self):
        movement_count = StockMovement.query.count()
        response = self.client_for(self.manager).post(
            f"/unassigned-invoices/{self.item.id}/clarify",
            data={
                "assigned_project_id": self.project.id,
                "assigned_device_id": self.device.id,
                "responsible_user_id": self.manager.id,
                "assignment_status": "unassigned",
                "notes": "Projekt és eszköz egyeztetve.",
            },
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.item)
        self.assertEqual(self.item.assignment_status, "assigned")
        self.assertEqual(self.item.assigned_project_id, self.project.id)
        self.assertEqual(self.item.assigned_device_id, self.device.id)
        self.assertEqual(self.item.responsible_user_id, self.manager.id)
        self.assertEqual(StockMovement.query.count(), movement_count)

        default_page = self.client_for(self.manager).get("/unassigned-invoices")
        self.assertNotIn("INV-001", default_page.get_data(as_text=True))

        assigned_page = self.client_for(self.manager).get(
            "/unassigned-invoices?assignment_status=assigned"
        )
        self.assertIn("INV-001", assigned_page.get_data(as_text=True))

        all_page = self.client_for(self.manager).get(
            "/unassigned-invoices?assignment_status=all"
        )
        self.assertIn("INV-001", all_page.get_data(as_text=True))

    def test_default_list_shows_empty_state_when_only_assigned_rows_exist(self):
        self.item.assignment_status = "assigned"
        self.item.assigned_project_id = self.project.id
        self.item.assigned_device_id = self.device.id
        db.session.commit()

        response = self.client_for(self.manager).get("/unassigned-invoices")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("INV-001", page)
        self.assertIn("Nincs rendezésre váró számlasor.", page)

    def test_manual_invoice_has_separate_page(self):
        response = self.client_for(self.manager).get("/unassigned-invoices")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('option value="unassigned" selected', page)
        self.assertIn("Rendezésre vár", page)
        self.assertIn("Manuális számlasor", page)
        self.assertNotIn("<h2>Számlasor létrehozása</h2>", page)
        self.assertEqual(
            self.client_for(self.manager).get("/unassigned-invoices/new").status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
