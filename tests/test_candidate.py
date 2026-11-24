"""FP-CAN-1, FP-CAN-2, and FP-CAN-3."""

from __future__ import annotations

from app import services
from tests.support import AppTestCase


class CandidateProfileTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.other = self.add_user("other@example.test", "Candidate", "Other")
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.job = self.add_job(self.employer)

    def test_fp_can_1_candidate_edits_own_profile_and_normalized_skills(self):
        self.login("cand@example.test")
        response = self.post(
            "/candidate/profile",
            {
                "display_name": "Cand Updated",
                "skills": " Python , SQL, python ,, Go ",
                "resume_text": "Private resume text.",
            },
        )
        self.assertEqual(response.status_code, 302)

        profile = self.call(services.get_candidate_profile, self.candidate)
        self.assertEqual(profile["display_name"], "Cand Updated")
        self.assertEqual(profile["skills"], ["go", "python", "sql"])
        self.assertEqual(profile["resume_text"], "Private resume text.")

        page = self.body(self.get("/candidate/profile"))
        self.assertIn("Cand Updated", page)
        self.assertIn("Private resume text.", page)

    def test_fp_can_1_profile_update_only_changes_the_signed_in_candidate(self):
        self.login("cand@example.test")
        self.post(
            "/candidate/profile",
            {"display_name": "Only Mine", "skills": "Python", "resume_text": "Mine"},
        )
        other_profile = self.call(services.get_candidate_profile, self.other)
        self.assertEqual(other_profile["display_name"], "Other")
        self.assertEqual(other_profile["skills"], [])
        self.assertEqual(other_profile["resume_text"], "")

    def test_fp_can_1_resume_owner_can_view_and_replace_it(self):
        self.login("cand@example.test")
        self.assertEqual(
            self.post(
                "/candidate/profile",
                {
                    "display_name": "Cand",
                    "skills": "",
                    "resume_text": "First version of the resume",
                },
            ).status_code,
            302,
        )
        page = self.get(f"/candidate/resume/{self.candidate}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("First version of the resume", self.body(page))

        self.post(
            "/candidate/profile",
            {
                "display_name": "Cand",
                "skills": "",
                "resume_text": "Replaced resume",
            },
        )
        self.assertIn(
            "Replaced resume", self.body(self.get(f"/candidate/resume/{self.candidate}"))
        )

    def test_fp_can_1_other_candidate_and_employer_cannot_read_resume(self):
        self.call(
            services.update_candidate_profile,
            self.candidate,
            "Cand",
            "Python",
            "TOP SECRET RESUME",
        )
        self.login("other@example.test")
        self.assertEqual(self.get(f"/candidate/resume/{self.candidate}").status_code, 403)
        self.assertNotIn("TOP SECRET", self.body(self.get(f"/candidate/resume/{self.candidate}")))
        self.logout()

        self.login("hr@example.test")
        self.assertEqual(self.get(f"/candidate/resume/{self.candidate}").status_code, 403)

    def test_fp_can_1_empty_display_name_is_rejected_without_saving(self):
        self.login("cand@example.test")
        response = self.post(
            "/candidate/profile",
            {"display_name": "   ", "skills": "Python", "resume_text": "x"},
        )
        self.assertEqual(response.status_code, 400)
        profile = self.call(services.get_candidate_profile, self.candidate)
        self.assertEqual(profile["display_name"], "Cand")
        self.assertEqual(profile["skills"], [])

    def test_fp_can_1_resume_text_is_not_used_for_matching(self):
        self.call(
            services.update_candidate_profile,
            self.candidate,
            "Cand",
            "Python",
            "I also know Rust, Kubernetes, and machine learning",
        )
        jobs = self.call(services.list_recommended_jobs, self.candidate)
        job = next(item for item in jobs if item["id"] == self.job)
        # Python matches one of two required skills: 50. The resume mentions
        # Rust and Kubernetes, which are deliberately not counted.
        self.assertEqual(job["score"], 50)

    def test_fp_can_2_dashboard_lists_jobs_with_score_and_fields(self):
        second = self.add_job(
            self.employer, "Data Analyst", "Python", "Analyze logistics data."
        )
        self.call(
            services.update_candidate_profile,
            self.candidate,
            "Cand",
            "Python, SQL",
            "",
        )
        self.login("cand@example.test")
        page = self.body(self.get("/candidate/"))

        self.assertIn("Backend Engineer", page)
        self.assertIn("Data Analyst", page)
        self.assertIn("Hiring Co", page)
        self.assertIn("python", page.lower())
        self.assertIn("100", page)
        self.assertIn("Analyze logistics data.", page)
        self.assertEqual(page.count("%"), 2)

    def test_fp_can_2_dashboard_sorted_highest_score_first(self):
        weak = self.add_job(self.employer, "Rust Role", "Rust", "Rust work.")
        self.call(
            services.update_candidate_profile,
            self.candidate,
            "Cand",
            "Python, SQL",
            "",
        )
        self.login("cand@example.test")
        jobs = self.call(services.list_recommended_jobs, self.candidate)
        self.assertEqual(jobs[0]["score"], 100)
        self.assertEqual(jobs[-1]["id"], weak)
        self.assertEqual(jobs[-1]["score"], 0)

    def test_fp_can_2_job_detail_shows_description(self):
        self.login("cand@example.test")
        response = self.get(f"/candidate/jobs/{self.job}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Build services.", self.body(response))


class CandidateApplicationTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.other = self.add_user("other@example.test", "Candidate", "Other")
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.job = self.add_job(self.employer)

    def test_fp_can_3_apply_creates_pending_application_once(self):
        self.login("cand@example.test")
        response = self.post(f"/candidate/jobs/{self.job}/apply")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count("applications"), 1)
        self.assertEqual(self.scalar("SELECT status FROM applications"), "Pending")

        duplicate = self.post(f"/candidate/jobs/{self.job}/apply")
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already applied", self.body(duplicate).lower())
        self.assertEqual(self.count("applications"), 1)

    def test_fp_can_3_candidate_sees_only_own_applications(self):
        other_job = self.add_job(self.employer, "Other Job", "Go")
        self.add_application(self.candidate, self.job, "Pending")
        self.add_application(self.other, other_job, "Accepted")

        self.login("cand@example.test")
        page = self.body(self.get("/candidate/applications"))
        self.assertIn("Backend Engineer", page)
        self.assertNotIn("Other Job", page)

        self.logout()
        self.login("other@example.test")
        page = self.body(self.get("/candidate/applications"))
        self.assertIn("Other Job", page)
        self.assertNotIn("Backend Engineer", page)

    def test_fp_can_3_applications_show_job_company_status_and_booking(self):
        application = self.add_application(self.candidate, self.job, "Interviewing")
        slot = self.add_slot(self.employer, self.job, booked_by_application=application)

        self.login("cand@example.test")
        page = self.body(self.get("/candidate/applications"))
        self.assertIn("Backend Engineer", page)
        self.assertIn("Hiring Co", page)
        self.assertIn("Interviewing", page)
        self.assertIn("UTC", page)

    def test_fp_can_3_candidate_cannot_change_application_status(self):
        application = self.add_application(self.candidate, self.job, "Pending")
        self.login("cand@example.test")
        response = self.post(
            f"/employer/applications/{application}/status", {"status": "Accepted"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.scalar("SELECT status FROM applications WHERE id = ?", (application,)),
            "Pending",
        )

    def test_fp_can_3_candidate_cannot_view_another_candidates_application_data(self):
        other_job = self.add_job(self.employer, "Other Job", "Go")
        self.add_application(self.other, other_job, "Accepted")
        self.login("cand@example.test")
        page = self.body(self.get("/candidate/applications"))
        self.assertNotIn("Other Job", page)
