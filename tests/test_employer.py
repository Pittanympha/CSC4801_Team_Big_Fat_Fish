"""FP-EMP-1, FP-EMP-2, and FP-EMP-3."""

from __future__ import annotations

from app import services
from tests.support import AppTestCase


class CompanyProfileTests(AppTestCase):
    def test_fp_emp_1_employer_views_and_edits_company_profile(self):
        employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.login("hr@example.test")

        page = self.body(self.get("/employer/company"))
        self.assertIn("Hiring Co", page)

        response = self.post(
            "/employer/company",
            {"company_name": "Acme Robotics", "description": "We build robots."},
        )
        self.assertEqual(response.status_code, 302)
        company = self.call(services.get_company_profile, employer)
        self.assertEqual(company["company_name"], "Acme Robotics")
        self.assertEqual(company["description"], "We build robots.")
        self.assertIn("Acme Robotics", self.body(self.get("/employer/company")))

    def test_fp_emp_1_empty_company_name_is_rejected(self):
        self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.login("hr@example.test")
        response = self.post("/employer/company", {"company_name": "", "description": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.scalar("SELECT company_name FROM employer_profiles"), "Hiring Co"
        )


class JobPostingTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.other_employer = self.add_user("other@example.test", "Employer", "Other Co")

    def test_fp_emp_2_create_read_update_delete_own_job(self):
        self.login("hr@example.test")
        response = self.post(
            "/employer/jobs/new",
            {
                "title": "Backend Engineer",
                "description": "Build APIs.",
                "skills": "Python, SQL",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count("jobs"), 1)
        job = self.fetchone("SELECT * FROM jobs")
        self.assertEqual(job["employer_id"], self.employer)

        dashboard = self.body(self.get("/employer/"))
        self.assertIn("Backend Engineer", dashboard)

        edit_page = self.body(self.get(f"/employer/jobs/{job['id']}/edit"))
        self.assertIn("Backend Engineer", edit_page)
        self.assertIn("Python, SQL", edit_page)

        update = self.post(
            f"/employer/jobs/{job['id']}/edit",
            {
                "title": "Senior Backend Engineer",
                "description": "Build and scale APIs.",
                "skills": "Python, SQL, Docker",
            },
        )
        self.assertEqual(update.status_code, 302)
        self.assertEqual(
            self.scalar("SELECT title FROM jobs WHERE id = ?", (job["id"],)),
            "Senior Backend Engineer",
        )
        skills = self.fetchall_skills(job["id"])
        self.assertEqual(skills, ["docker", "python", "sql"])

        delete = self.post(f"/employer/jobs/{job['id']}/delete")
        self.assertEqual(delete.status_code, 302)
        self.assertEqual(self.count("jobs"), 0)

    def fetchall_skills(self, job_id: int):
        with self.app.app_context():
            from app.db import get_db

            return [
                row["skill"]
                for row in get_db()
                .execute("SELECT skill FROM job_skills WHERE job_id = ? ORDER BY skill", (job_id,))
                .fetchall()
            ]

    def test_fp_emp_2_job_requires_title_and_description(self):
        self.login("hr@example.test")
        response = self.post(
            "/employer/jobs/new", {"title": "", "description": "", "skills": "Python"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("jobs"), 0)

        job = self.add_job(self.employer, "Valid", "Python", "Valid description.")
        response = self.post(
            f"/employer/jobs/{job}/edit",
            {"title": "Changed", "description": "", "skills": "Python"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.scalar("SELECT title FROM jobs WHERE id = ?", (job,)), "Valid"
        )

    def test_fp_emp_2_other_employer_cannot_edit_or_delete_job(self):
        job = self.add_job(self.employer)
        self.login("other@example.test")
        self.assertEqual(self.get(f"/employer/jobs/{job}/edit").status_code, 403)
        self.assertEqual(
            self.post(
                f"/employer/jobs/{job}/edit",
                {"title": "Hijacked", "description": "No", "skills": ""},
            ).status_code,
            403,
        )
        self.assertEqual(self.post(f"/employer/jobs/{job}/delete").status_code, 403)
        self.assertEqual(self.count("jobs"), 1)

    def test_fp_emp_2_delete_job_with_application_returns_409(self):
        candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        job = self.add_job(self.employer)
        self.add_application(candidate, job, "Pending")
        self.login("hr@example.test")

        response = self.post(f"/employer/jobs/{job}/delete")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count("jobs"), 1)
        self.assertEqual(self.count("applications"), 1)

    def test_fp_emp_2_delete_job_with_slot_returns_409(self):
        job = self.add_job(self.employer)
        self.add_slot(self.employer, job)
        self.login("hr@example.test")

        response = self.post(f"/employer/jobs/{job}/delete")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count("jobs"), 1)
        self.assertEqual(self.count("interview_slots"), 1)

    def test_fp_emp_2_job_without_dependents_is_deletable(self):
        job = self.add_job(self.employer)
        self.login("hr@example.test")
        self.assertEqual(self.post(f"/employer/jobs/{job}/delete").status_code, 302)
        self.assertEqual(self.count("jobs"), 0)
        self.assertEqual(self.count("job_skills"), 0)


class ApplicantManagementTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.other_employer = self.add_user("other@example.test", "Employer", "Other Co")
        self.job = self.add_job(self.employer, "Backend", "Python, SQL")
        self.strong = self.add_user("strong@example.test", "Candidate", "Alice Strong")
        self.weak = self.add_user("weak@example.test", "Candidate", "Bob Weak")
        self.call(
            services.update_candidate_profile,
            self.strong,
            "Alice Strong",
            "Python, SQL",
            "Secret resume for Alice",
        )
        self.call(
            services.update_candidate_profile,
            self.weak,
            "Bob Weak",
            "Python",
            "Secret resume for Bob",
        )
        self.strong_app = self.add_application(self.strong, self.job, "Pending")
        self.weak_app = self.add_application(self.weak, self.job, "Pending")

    def test_fp_emp_3_applicants_sorted_with_identity_skills_score_status(self):
        self.login("hr@example.test")
        page = self.body(self.get(f"/employer/jobs/{self.job}/applicants"))
        self.assertIn("Alice Strong", page)
        self.assertIn("strong@example.test", page)
        self.assertIn("Bob Weak", page)
        self.assertIn("python", page.lower())
        self.assertIn("Pending", page)
        self.assertIn("100", page)
        self.assertIn("50", page)
        self.assertLess(page.index("Alice Strong"), page.index("Bob Weak"))

    def test_fp_emp_3_all_four_statuses_can_be_set(self):
        self.login("hr@example.test")
        for status in ("Interviewing", "Rejected", "Accepted", "Pending"):
            response = self.post(
                f"/employer/applications/{self.strong_app}/status", {"status": status}
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                self.scalar(
                    "SELECT status FROM applications WHERE id = ?", (self.strong_app,)
                ),
                status,
            )

    def test_fp_emp_3_invalid_status_is_rejected(self):
        self.login("hr@example.test")
        response = self.post(
            f"/employer/applications/{self.strong_app}/status", {"status": "Hired"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.scalar(
                "SELECT status FROM applications WHERE id = ?", (self.strong_app,)
            ),
            "Pending",
        )

    def test_fp_emp_3_other_employer_cannot_view_or_change_applicants(self):
        self.login("other@example.test")
        self.assertEqual(
            self.get(f"/employer/jobs/{self.job}/applicants").status_code, 403
        )
        response = self.post(
            f"/employer/applications/{self.strong_app}/status", {"status": "Rejected"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.scalar(
                "SELECT status FROM applications WHERE id = ?", (self.strong_app,)
            ),
            "Pending",
        )

    def test_fp_emp_3_candidate_cannot_change_status(self):
        self.login("strong@example.test")
        response = self.post(
            f"/employer/applications/{self.strong_app}/status", {"status": "Accepted"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.scalar(
                "SELECT status FROM applications WHERE id = ?", (self.strong_app,)
            ),
            "Pending",
        )

    def test_fp_emp_3_applicant_list_does_not_expose_resumes(self):
        self.login("hr@example.test")
        page = self.body(self.get(f"/employer/jobs/{self.job}/applicants"))
        self.assertNotIn("Secret resume for Alice", page)
        self.assertNotIn("Secret resume for Bob", page)
