import unittest
from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from werkzeug.security import generate_password_hash

from app import create_app, db, m2m_package_limit_mb, m2m_usage_state
from models import (
    Device,
    M2MMonthlyUsage,
    M2MPackageHistory,
    M2MSubscription,
    User,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "m2m-test"
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


class M2MWorkflowTestCase(unittest.TestCase):
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
        self.device = Device(
            asset_tag="RUT-001",
            product_name="Teltonika RUT241",
            device_type="Router",
            quantity=1,
        )
        self.subscription = M2MSubscription(
            subscriber_name="Parkl",
            phone_number="+36301234567",
            sim_number="8944100000001",
            location_name="Arena",
            device_identifier="RUT241-001",
            current_package="1 GB",
            current_monthly_fee=1990,
            status="active",
            teltonika_device=self.device,
        )
        db.session.add_all(
            [self.manager, self.technician, self.device, self.subscription]
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

    def test_m2m_permissions_and_usage_thresholds(self):
        manager_client = self.client_for(self.manager)
        self.assertEqual(manager_client.get("/m2m").status_code, 200)
        template_response = manager_client.get("/m2m/import/template")
        self.assertEqual(template_response.status_code, 200)
        self.assertEqual(
            template_response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        denied = self.client_for(self.technician).get("/m2m")
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(denied.headers["Location"], "/dashboard")

        self.assertEqual(m2m_package_limit_mb("1 GB"), 1024)
        self.assertEqual(m2m_usage_state("1 GB", 850)["key"], "warning")
        self.assertEqual(m2m_usage_state("1 GB", 1100)["key"], "exceeded")
        self.assertEqual(m2m_usage_state("Korlátlan", 5000)["key"], "unknown")

    def test_usage_upsert_and_detail_chart(self):
        today = date.today()
        client = self.client_for(self.manager)
        first = client.post(
            f"/m2m/{self.subscription.id}/usage",
            data={
                "year": today.year,
                "month": today.month,
                "usage_mb": "820",
                "source": "manual",
            },
        )
        self.assertEqual(first.status_code, 302)
        second = client.post(
            f"/m2m/{self.subscription.id}/usage",
            data={
                "year": today.year,
                "month": today.month,
                "usage_mb": "900",
                "source": "manual",
            },
        )
        self.assertEqual(second.status_code, 302)
        self.assertEqual(M2MMonthlyUsage.query.count(), 1)
        self.assertEqual(float(M2MMonthlyUsage.query.one().usage_mb), 900)

        page = client.get(f"/m2m/{self.subscription.id}")
        html = page.get_data(as_text=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Limit közelében", html)
        self.assertIn("chart.js", html)

    def test_package_change_closes_previous_package(self):
        previous = M2MPackageHistory(
            subscription_id=self.subscription.id,
            package_name="500 MB",
            monthly_fee=1200,
            valid_from=date(2026, 1, 1),
        )
        db.session.add(previous)
        db.session.commit()

        response = self.client_for(self.manager).post(
            f"/m2m/{self.subscription.id}/package",
            data={
                "package_name": "2 GB",
                "monthly_fee": "2490",
                "valid_from": "2026-06-01",
                "notes": "Bővítés",
            },
        )
        self.assertEqual(response.status_code, 302)
        db.session.refresh(previous)
        db.session.refresh(self.subscription)
        self.assertEqual(previous.valid_to, date(2026, 5, 31))
        self.assertEqual(self.subscription.current_package, "2 GB")
        self.assertEqual(M2MPackageHistory.query.count(), 2)

    def test_xlsx_import_updates_by_sim_and_imports_monthly_usage(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Előfizető",
                "Hívószám",
                "SIM",
                "Helyszín",
                "Csomag",
                "Havidíj",
                "Státusz",
                "2026-06 forgalom (MB)",
            ]
        )
        sheet.append(
            [
                "Parkl frissítve",
                "+36309999999",
                self.subscription.sim_number,
                "Office Park",
                "2 GB",
                2490,
                "Aktív",
                640,
            ]
        )
        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)

        response = self.client_for(self.manager).post(
            "/m2m/import",
            data={"m2m_file": (stream, "m2m.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(M2MSubscription.query.count(), 1)
        db.session.refresh(self.subscription)
        self.assertEqual(self.subscription.location_name, "Office Park")
        self.assertEqual(self.subscription.current_package, "2 GB")
        usage = M2MMonthlyUsage.query.filter_by(
            subscription_id=self.subscription.id,
            year=2026,
            month=6,
            source="import",
        ).one()
        self.assertEqual(float(usage.usage_mb), 640)


if __name__ == "__main__":
    unittest.main()
