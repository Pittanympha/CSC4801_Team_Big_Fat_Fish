"""FP-SEC-1 through FP-SEC-4: authorization boundaries, injection, XSS, secrets."""

from __future__ import annotations

from pathlib import Path

from app import services
from tests.support import AppTestCase, TEST_TMP_ROOT

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ObjectAccessTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.other_employer = self.add_user("other.hr@example.test", "Employer", "Other Co")
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.other_candidate = self.add_user("other@example.test", "Candidate", "Other")
        self.job = self.add_job(self.employer)
        self.application = self.add_application(self.candidate, self.job, "Interviewing")
        self.other_application = self.add_application(
            self.other_candidate, self.job, "Interviewing"
        )
        self.slot = self.add_slot(self.employer, self.job)

    def test_fp_sec_1_candidate_cannot_read_or_modify_another_candidates_data(self):
        self.call(
            services.update_candidate_profile,
            self.other_candidate,
            "Other",
            "Rust",
            "OTHER PRIVATE RESUME",
        )
        self.login("cand@example.test")

        resume = self.get(f"/candidate/resume/{self.other_candidate}")
        self.assertEqual(resume.status_code, 403)
        self.assertNotIn("OTHER PRIVATE RESUME", self.body(resume))

        booking = self.post(
            f"/candidate/applications/{self.other_application}/book",
            {"slot_id": self.slot},
        )
        self.assertEqual(booking.status_code, 403)
        self.assertEqual(self.count("bookings"), 0)

        page = self.body(self.get("/candidate/applications"))
        self.assertNotIn("OTHER PRIVATE RESUME", page)

    def test_fp_sec_1_employer_cannot_modify_another_job_or_read_applicants(self):
        self.login("other.hr@example.test")
        self.assertEqual(self.get(f"/employer/jobs/{self.job}/edit").status_code, 403)
        self.assertEqual(
            self.get(f"/employer/jobs/{self.job}/applicants").status_code, 403
        )
        response = self.post(
            f"/employer/applications/{self.application}/status", {"status": "Rejected"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.scalar("SELECT status FROM applications WHERE id = ?", (self.application,)),
            "Interviewing",
        )

    def test_fp_sec_1_candidate_cannot_book_with_another_candidates_application(self):
        self.login("other@example.test")
        response = self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": self.slot}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.count("bookings"), 0)


class SqlInjectionTests(AppTestCase):
    def test_fp_sec_2_sql_injection_in_login_cannot_bypass_authentication(self):
        self.add_user("real@example.test", "Candidate", "Real")
        for email in ("' OR '1'='1' --", "real@example.test' OR 1=1 --", "'; DROP TABLE users; --"):
            with self.subTest(email=email):
                response = self.client.post(
                    "/login", data={"email": email, "password": "anything"}
                )
                self.assertEqual(response.status_code, 401)
        self.assertEqual(self.count("users"), 1)

    def test_fp_sec_2_sql_metacharacters_are_bound_not_executed(self):
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.login("cand@example.test")
        payload = "Python'); DROP TABLE users;--"
        response = self.post(
            "/candidate/profile",
            {"display_name": "Cand", "skills": payload, "resume_text": "safe"},
        )
        self.assertEqual(response.status_code, 302)

        # The table still exists and the payload is stored as a literal value.
        table_count = self.scalar(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        )
        self.assertEqual(table_count, 1)
        self.assertEqual(self.count("users"), 1)
        stored = self.scalar("SELECT skill FROM candidate_skills WHERE user_id = ?", (candidate,))
        self.assertEqual(stored, payload.lower())
        self.assertIn("python", self.body(self.get("/candidate/profile")).lower())

    def test_fp_sec_2_sql_metacharacters_in_job_text_are_bound(self):
        employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        job = self.add_job(
            employer,
            "Engineer'); DROP TABLE jobs;--",
            "Python",
            "Description'); DELETE FROM applications;--",
        )

        jobs = self.call(services.list_recommended_jobs, candidate)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], job)
        self.assertEqual(self.count("jobs"), 1)
        self.assertEqual(self.count("applications"), 0)


class XssTests(AppTestCase):
    def test_fp_sec_3_profile_display_name_is_escaped(self):
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.login("cand@example.test")
        payload = "<script>alert(1)</script>"
        self.post(
            "/candidate/profile",
            {"display_name": payload, "skills": "", "resume_text": ""},
        )
        page = self.body(self.get("/candidate/profile"))
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_fp_sec_3_resume_text_is_escaped(self):
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.login("cand@example.test")
        payload = "<script>alert(2)</script>"
        self.post(
            "/candidate/profile",
            {"display_name": "Cand", "skills": "", "resume_text": payload},
        )
        page = self.body(self.get(f"/candidate/resume/{candidate}"))
        self.assertNotIn(payload, page)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", page)

    def test_fp_sec_3_job_and_company_text_is_escaped(self):
        employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        payload = "<img src=x onerror=alert(3)>"
        job = self.add_job(employer, "Role", "Python", payload)
        self.call(services.update_company_profile, employer, "Acme", payload)

        self.login("cand@example.test")
        dashboard = self.body(self.get("/candidate/"))
        self.assertNotIn(payload, dashboard)
        detail = self.body(self.get(f"/candidate/jobs/{job}"))
        self.assertNotIn(payload, detail)
        self.assertIn("&lt;img", detail)

        self.logout()
        self.login("hr@example.test")
        company_page = self.body(self.get("/employer/company"))
        self.assertNotIn(payload, company_page)
        self.assertIn("&lt;img", company_page)


class SecretsAndTestIsolationTests(AppTestCase):
    def test_fp_sec_4_env_example_contains_placeholders_only(self):
        example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("SECRET_KEY=", example)
        self.assertIn("replace-with", example.lower())
        self.assertIn("DATABASE_PATH=", example)
        self.assertNotRegex(example, r"SECRET_KEY=(?!replace)[A-Za-z0-9+/=]{20,}")

    def test_fp_sec_4_no_env_file_is_committed(self):
        self.assertFalse((PROJECT_ROOT / ".env").exists())

    def test_fp_sec_4_tests_use_an_isolated_database(self):
        self.assertTrue(str(self.db_path).startswith(str(TEST_TMP_ROOT)))
        self.assertNotEqual(self.db_path, str(PROJECT_ROOT / "instance" / "app.db"))
        self.assertIn("test-tmp", self.db_path)

    def test_fp_sec_4_no_obvious_production_secret_in_source(self):
        patterns = ("sk_live_", "AKIA", "BEGIN RSA PRIVATE KEY", "postgres://user:pass")
        for path in (PROJECT_ROOT / "app").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                with self.subTest(path=path.name, pattern=pattern):
                    self.assertNotIn(pattern, text)
