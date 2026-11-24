"""FP-MATCH-1: deterministic skill-overlap score and both tie-break rules."""

from __future__ import annotations

import unittest

from app import services
from app.matching import calculate_match_score, normalize_skills
from tests.support import AppTestCase


class MatchingFormulaTests(unittest.TestCase):
    def test_fp_match_1_required_examples(self):
        cases = [
            ("Python, SQL", "Python, SQL", 100),
            ("Python", "Python, SQL", 50),
            ("Rust", "Python, SQL", 0),
            ("anything, at all", "", 100),
        ]
        for candidate, required, expected in cases:
            with self.subTest(candidate=candidate, required=required):
                self.assertEqual(calculate_match_score(candidate, required), expected)

    def test_fp_match_1_normalizes_whitespace_case_and_duplicates(self):
        self.assertEqual(
            normalize_skills(" Python , sql, , PYTHON ,  "),
            {"python", "sql"},
        )
        self.assertEqual(
            calculate_match_score([" Python ", "PYTHON"], ["python", "sql"]),
            50,
        )

    def test_fp_match_1_empty_required_set_scores_one_hundred(self):
        self.assertEqual(calculate_match_score([], []), 100)
        self.assertEqual(calculate_match_score("Rust", None), 100)

    def test_fp_match_1_score_is_integer_floor_between_0_and_100(self):
        score = calculate_match_score(["a"], ["a", "b", "c"])
        self.assertEqual(score, 33)
        self.assertIsInstance(score, int)
        self.assertEqual(calculate_match_score([], ["a"]), 0)
        self.assertEqual(calculate_match_score(["a"], ["a"]), 100)


class MatchingOrderingTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.call(
            services.update_candidate_profile,
            self.candidate,
            "Cand",
            "Python, SQL",
            "resume",
        )

    def test_fp_match_1_candidate_dashboard_sorts_score_title_then_id(self):
        zeta = self.add_job(self.employer, "Zeta", "Python, SQL")
        alpha = self.add_job(self.employer, "alpha", "Python, SQL")
        alpha_upper = self.add_job(self.employer, "Alpha", "Python, SQL")
        beta = self.add_job(self.employer, "Beta", "Go")

        jobs = self.call(services.list_recommended_jobs, self.candidate)
        self.assertEqual([job["id"] for job in jobs], [alpha, alpha_upper, zeta, beta])
        self.assertEqual([job["score"] for job in jobs], [100, 100, 100, 0])

    def test_fp_match_1_employer_applicants_sort_score_name_then_id(self):
        job = self.add_job(self.employer, "Backend", "Python, SQL")
        zoe = self.add_user("zoe@example.test", "Candidate", "Zoe")
        alice = self.add_user("alice@example.test", "Candidate", "Alice")
        alice_lower = self.add_user("alice2@example.test", "Candidate", "alice")
        bob = self.add_user("bob@example.test", "Candidate", "Bob")
        profiles = {
            zoe: ("Zoe", "Python, SQL"),
            alice: ("Alice", "Python, SQL"),
            alice_lower: ("alice", "Python, SQL"),
            bob: ("Bob", "Python"),
        }
        for candidate, (name, skills) in profiles.items():
            self.call(services.update_candidate_profile, candidate, name, skills, "")
            self.add_application(candidate, job, "Pending")

        applicants = self.call(services.list_applicants, self.employer, job)
        self.assertEqual(
            [row["candidate_id"] for row in applicants],
            [alice, alice_lower, zoe, bob],
        )
        self.assertEqual([row["score"] for row in applicants], [100, 100, 100, 50])

    def test_fp_match_1_same_score_in_candidate_and_employer_views(self):
        job = self.add_job(self.employer, "Backend", "Python, SQL")
        self.add_application(self.candidate, job, "Pending")

        candidate_view = {
            item["id"]: item["score"]
            for item in self.call(services.list_recommended_jobs, self.candidate)
        }
        employer_view = {
            item["candidate_id"]: item["score"]
            for item in self.call(services.list_applicants, self.employer, job)
        }
        self.assertEqual(candidate_view[job], employer_view[self.candidate])
        self.assertEqual(candidate_view[job], 100)
