"""Browser-level smoke checks for the seeded demo (all pages render)."""

from __future__ import annotations

from app.seed import DEMO_PASSWORD, seed_database
from tests.support import AppTestCase


class UiSmokeTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.call(seed_database, True)

    def test_public_pages_and_health_endpoint_render(self):
        for path in ("/", "/login", "/register", "/healthz"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 200)

    def test_static_stylesheet_is_served(self):
        response = self.get("/static/style.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.content_type)

    def test_candidate_pages_render(self):
        self.login("alice@demo.test", DEMO_PASSWORD)
        for path in (
            "/candidate/",
            "/candidate/profile",
            "/candidate/applications",
            "/candidate/jobs/1",
        ):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("TalentBridge", self.body(response))

    def test_employer_pages_render(self):
        self.login("hr@acme.test", DEMO_PASSWORD)
        for path in (
            "/employer/",
            "/employer/company",
            "/employer/jobs/new",
            "/employer/jobs/1/edit",
            "/employer/jobs/1/applicants",
            "/employer/jobs/1/slots",
        ):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("TalentBridge", self.body(response))

    def test_unknown_page_returns_styled_404(self):
        response = self.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Not found", self.body(response))

    def test_login_page_does_not_render_password_values(self):
        page = self.body(self.get("/login"))
        self.assertNotIn("DemoPass123!", page)
