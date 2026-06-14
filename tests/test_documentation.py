import unittest
from datetime import timedelta

from werkzeug.security import generate_password_hash

from app import create_app, db
from models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "documentation-test"
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


class DocumentationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(
            username="viewer",
            password_hash=generate_password_hash("ViewerTest123!"),
            role="viewer",
            is_active=True,
            force_password_change=False,
        )
        db.session.add(self.user)
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

    def test_documentation_landing_and_module_pages(self):
        client = self.client()
        landing = client.get("/help")
        self.assertEqual(landing.status_code, 200)
        page = landing.get_data(as_text=True)
        self.assertIn("Hogyan működik az Infra Manager?", page)
        self.assertIn("Dokumentációs területek", page)

        for slug, heading in (
            ("overview", "Rendszer áttekintés"),
            ("devices", "Eszközök"),
            ("finance", "Pénzügyi modul"),
            ("workflows", "Munkafolyamatok"),
            ("technology", "Technológiai háttér"),
            ("roadmap", "Roadmap"),
        ):
            response = client.get(f"/help/{slug}")
            self.assertEqual(response.status_code, 200)
            self.assertIn(heading, response.get_data(as_text=True))

    def test_documentation_search_uses_keywords_and_content(self):
        response = self.client().get("/help/search?q=ICCID")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("M2M SIM-ek", page)
        self.assertIn("Integrációk", page)
        self.assertIn("találat", page)

    def test_version_page_renders_runtime_information(self):
        response = self.client().get("/help/version")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Git commit", page)
        self.assertIn("Adatbázis migráció", page)
        self.assertIn("sqlite", page)

    def test_unknown_documentation_page_returns_404(self):
        self.assertEqual(self.client().get("/help/nincs-ilyen").status_code, 404)
