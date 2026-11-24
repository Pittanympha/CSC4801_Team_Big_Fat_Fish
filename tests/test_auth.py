"""FP-AUTH-1, FP-AUTH-2, and FP-AUTH-3."""

from __future__ import annotations

from tests.support import AppTestCase, DEFAULT_PASSWORD


class RegistrationAndSessionTests(AppTestCase):
    def test_fp_auth_1_candidate_register_login_logout(self):
        response = self.post(
            "/register",
            {
                "email": "new.candidate@example.test",
                "display_name": "New Candidate",
                "password": "SecurePass123!",
                "role": "Candidate",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/candidate/", response.headers["Location"])
        self.assertEqual(self.count("users"), 1)
        self.assertEqual(self.count("candidate_profiles"), 1)
        self.assertEqual(self.scalar("SELECT role FROM users"), "Candidate")

        # The registration logs the new account in.
        self.assertEqual(self.get("/candidate/").status_code, 200)

        logout = self.post("/logout")
        self.assertEqual(logout.status_code, 302)
        protected = self.get("/candidate/")
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/login", protected.headers["Location"])

        self.login("new.candidate@example.test", "SecurePass123!")
        self.assertEqual(self.get("/candidate/").status_code, 200)

    def test_fp_auth_1_employer_register_creates_company_profile(self):
        response = self.post(
            "/register",
            {
                "email": "new.employer@example.test",
                "display_name": "Hiring Team",
                "password": "SecurePass123!",
                "role": "Employer",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/employer/", response.headers["Location"])
        self.assertEqual(
            self.scalar("SELECT company_name FROM employer_profiles"), "Hiring Team"
        )
        self.assertEqual(self.get("/employer/").status_code, 200)

    def test_fp_auth_1_email_is_unique_case_insensitively(self):
        data = {
            "email": "Person@Example.Test",
            "display_name": "Person",
            "password": "SecurePass123!",
            "role": "Candidate",
        }
        self.assertEqual(self.post("/register", data).status_code, 302)
        self.logout()

        duplicate = dict(data)
        duplicate["email"] = "person@example.test"
        duplicate["display_name"] = "Someone Else"
        response = self.post("/register", duplicate)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", self.body(response))
        self.assertEqual(self.count("users"), 1)

    def test_fp_auth_1_only_two_roles_are_accepted(self):
        response = self.post(
            "/register",
            {
                "email": "admin@example.test",
                "display_name": "Admin",
                "password": "SecurePass123!",
                "role": "Admin",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("users"), 0)

    def test_fp_auth_2_passwords_are_hashed_and_never_rendered(self):
        password = "VerySecret123!"
        self.post(
            "/register",
            {
                "email": "hash@example.test",
                "display_name": "Hash Tester",
                "password": password,
                "role": "Candidate",
            },
        )
        password_hash = self.scalar("SELECT password_hash FROM users")
        self.assertTrue(password_hash.startswith("scrypt:"))
        self.assertNotIn(password, password_hash)

        body = self.body(self.get("/candidate/profile"))
        self.assertNotIn(password, body)
        self.assertNotIn(password_hash, body)
        self.assertNotIn("password_hash", body)

    def test_fp_auth_2_short_password_is_rejected(self):
        response = self.post(
            "/register",
            {
                "email": "short@example.test",
                "display_name": "Short",
                "password": "short",
                "role": "Candidate",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("users"), 0)

    def test_fp_auth_1_bad_login_returns_401(self):
        self.add_user("known@example.test", "Candidate", "Known")
        response = self.client.post(
            "/login", data={"email": "known@example.test", "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("incorrect", self.body(response).lower())
        unknown = self.client.post(
            "/login", data={"email": "missing@example.test", "password": DEFAULT_PASSWORD}
        )
        self.assertEqual(unknown.status_code, 401)


class AuthorizationContractTests(AppTestCase):
    def test_fp_auth_3_unauthenticated_get_redirects_to_login(self):
        response = self.get("/candidate/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_fp_auth_3_unauthenticated_post_returns_401(self):
        response = self.post("/candidate/jobs/1/apply")
        self.assertEqual(response.status_code, 401)

    def test_fp_auth_3_wrong_role_returns_403(self):
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        employer = self.add_user("emp@example.test", "Employer", "Emp")

        self.login("cand@example.test")
        self.assertEqual(self.get("/employer/").status_code, 403)
        self.logout()

        self.login("emp@example.test")
        self.assertEqual(self.get("/candidate/").status_code, 403)
        self.assertEqual(self.get(f"/candidate/resume/{candidate}").status_code, 403)

    def test_fp_auth_3_missing_object_returns_404(self):
        self.add_user("emp@example.test", "Employer", "Emp")
        self.login("emp@example.test")
        self.assertEqual(self.get("/employer/jobs/9999/edit").status_code, 404)
        self.logout()

        self.add_user("cand2@example.test", "Candidate", "Cand")
        self.login("cand2@example.test")
        self.assertEqual(self.get("/candidate/jobs/9999").status_code, 404)

    def test_fp_auth_3_other_candidates_resume_returns_403(self):
        owner = self.add_user("owner@example.test", "Candidate", "Owner")
        other = self.add_user("other@example.test", "Candidate", "Other")
        self.login("other@example.test")
        response = self.get(f"/candidate/resume/{owner}")
        self.assertEqual(response.status_code, 403)

    def test_fp_auth_3_other_employers_job_returns_403(self):
        owner = self.add_user("owner@example.test", "Employer", "Owner Co")
        intruder = self.add_user("intruder@example.test", "Employer", "Intruder Co")
        job = self.add_job(owner)
        self.login("intruder@example.test")

        self.assertEqual(self.get(f"/employer/jobs/{job}/edit").status_code, 403)
        self.assertEqual(self.get(f"/employer/jobs/{job}/applicants").status_code, 403)
        self.assertEqual(self.post(f"/employer/jobs/{job}/delete").status_code, 403)

    def test_fp_auth_3_session_role_cannot_be_forged(self):
        candidate = self.add_user("forge@example.test", "Candidate", "Forge")
        self.login("forge@example.test")
        with self.client.session_transaction() as session:
            session["role"] = "Employer"
        self.assertEqual(self.get("/employer/").status_code, 403)
        self.assertEqual(self.get("/candidate/").status_code, 200)
