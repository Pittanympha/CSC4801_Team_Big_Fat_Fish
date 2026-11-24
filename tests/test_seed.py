"""FP-DOC-3 deterministic seed data and demo accounts."""

from __future__ import annotations

from app import services
from app.constants import APPLICATION_STATUSES
from app.seed import DEMO_ACCOUNTS, DEMO_PASSWORD, seed_database
from tests.support import AppTestCase


class SeedDataTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.summary = self.call(seed_database, True)

    def test_fp_doc_3_seed_has_required_users_jobs_and_applications(self):
        self.assertEqual(self.count("users"), 7)
        self.assertGreaterEqual(self.count("candidate_profiles"), 2)
        self.assertGreaterEqual(self.count("employer_profiles"), 2)
        self.assertEqual(self.count("jobs"), 4)
        self.assertEqual(self.count("applications"), 6)
        self.assertEqual(self.count("interview_slots"), 3)
        self.assertEqual(self.count("bookings"), 1)

    def test_fp_doc_3_seed_covers_all_four_application_statuses(self):
        statuses = {
            row["status"]
            for row in self.fetchall("SELECT status FROM applications")
        }
        self.assertEqual(statuses, set(APPLICATION_STATUSES))

    def test_fp_doc_3_seed_contains_the_four_matching_examples(self):
        alice = self.user_id("alice@demo.test")
        bob = self.user_id("bob@demo.test")
        carol = self.user_id("carol@demo.test")
        jobs = self.call(services.list_recommended_jobs, alice)
        by_title = {job["title"]: job for job in jobs}
        backend = by_title["Backend Engineer"]
        generalist = by_title["Junior Generalist"]

        self.assertEqual(backend["score"], 100)  # Python+SQL vs Python+SQL
        self.assertEqual(generalist["score"], 100)  # empty required list

        bob_jobs = self.call(services.list_recommended_jobs, bob)
        self.assertEqual(
            next(job for job in bob_jobs if job["title"] == "Backend Engineer")["score"],
            50,
        )
        carol_jobs = self.call(services.list_recommended_jobs, carol)
        self.assertEqual(
            next(job for job in carol_jobs if job["title"] == "Backend Engineer")["score"],
            0,
        )

    def test_fp_doc_3_seed_has_two_interviewing_candidates_racing_for_one_slot(self):
        dave = self.user_id("dave@demo.test")
        erin = self.user_id("erin@demo.test")
        dave_apps = [
            app
            for app in self.call(services.list_candidate_applications, dave)
            if app["status"] == "Interviewing"
        ]
        erin_apps = [
            app
            for app in self.call(services.list_candidate_applications, erin)
            if app["status"] == "Interviewing"
        ]
        self.assertEqual(len(dave_apps), 1)
        self.assertEqual(len(erin_apps), 1)
        self.assertIsNone(dave_apps[0]["booking_id"])
        self.assertIsNone(erin_apps[0]["booking_id"])

        dave_slots = {slot["id"] for slot in dave_apps[0]["available_slots"]}
        erin_slots = {slot["id"] for slot in erin_apps[0]["available_slots"]}
        self.assertTrue(dave_slots & erin_slots)
        self.assertIn(self.summary["race_slot_id"], dave_slots)
        self.assertIn(self.summary["race_slot_id"], erin_slots)

    def test_fp_doc_3_seed_accounts_are_documented_demo_credentials(self):
        emails = {account["email"] for account in DEMO_ACCOUNTS}
        self.assertEqual(
            emails,
            {
                "alice@demo.test",
                "bob@demo.test",
                "carol@demo.test",
                "dave@demo.test",
                "erin@demo.test",
                "hr@acme.test",
                "hr@globex.test",
            },
        )
        self.assertEqual(DEMO_PASSWORD, "DemoPass123!")
        # Seeded accounts can actually log in with the documented password.
        self.login("alice@demo.test", DEMO_PASSWORD)
        self.assertEqual(self.get("/candidate/").status_code, 200)

    def test_fp_doc_3_seed_is_idempotent_and_deterministic(self):
        first = {
            "users": self.count("users"),
            "jobs": self.count("jobs"),
            "applications": self.count("applications"),
            "slots": self.count("interview_slots"),
            "bookings": self.count("bookings"),
            "emails": sorted(
                row["email"] for row in self.fetchall("SELECT email FROM users")
            ),
        }
        self.call(seed_database, True)
        second = {
            "users": self.count("users"),
            "jobs": self.count("jobs"),
            "applications": self.count("applications"),
            "slots": self.count("interview_slots"),
            "bookings": self.count("bookings"),
            "emails": sorted(
                row["email"] for row in self.fetchall("SELECT email FROM users")
            ),
        }
        self.assertEqual(first, second)

    # -- helpers -----------------------------------------------------------
    def fetchall(self, sql: str, params=()):
        with self.app.app_context():
            from app.db import get_db

            return [dict(row) for row in get_db().execute(sql, params).fetchall()]

    def user_id(self, email: str) -> int:
        return self.scalar("SELECT id FROM users WHERE email = ?", (email,))
