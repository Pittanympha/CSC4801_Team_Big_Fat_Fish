"""FP-SCHED-1, FP-SCHED-2, and FP-SCHED-3."""

from __future__ import annotations

import threading
from datetime import timedelta

from app import services
from app.errors import AppError
from app.timeutil import format_utc, utc_now
from tests.support import AppTestCase


class AvailabilityTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.other = self.add_user("other@example.test", "Employer", "Other Co")
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.job = self.add_job(self.employer)
        self.application = self.add_application(self.candidate, self.job, "Pending")

    def _form_times(self, hours: int = 3, minutes: int = 30):
        start = utc_now() + timedelta(hours=hours)
        end = start + timedelta(minutes=minutes)
        return start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")

    def test_fp_sched_1_employer_creates_thirty_minute_future_slot(self):
        self.login("hr@example.test")
        start, end = self._form_times()
        response = self.post(
            f"/employer/jobs/{self.job}/slots", {"start_at": start, "end_at": end}
        )
        self.assertEqual(response.status_code, 302)
        slot = self.fetchone("SELECT * FROM interview_slots")
        self.assertEqual(slot["job_id"], self.job)
        self.assertEqual(slot["employer_id"], self.employer)
        self.assertEqual(slot["start_at"], start + ":00Z")
        self.assertEqual(slot["end_at"], end + ":00Z")

    def test_fp_sched_1_rejects_non_thirty_minute_duration(self):
        self.login("hr@example.test")
        start, end = self._form_times(minutes=60)
        response = self.post(
            f"/employer/jobs/{self.job}/slots", {"start_at": start, "end_at": end}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("30 minutes", self.body(response))
        self.assertEqual(self.count("interview_slots"), 0)

    def test_fp_sched_1_rejects_end_before_start(self):
        self.login("hr@example.test")
        start = utc_now() + timedelta(hours=3)
        end = start - timedelta(minutes=30)
        response = self.post(
            f"/employer/jobs/{self.job}/slots",
            {
                "start_at": start.strftime("%Y-%m-%dT%H:%M"),
                "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("interview_slots"), 0)

    def test_fp_sched_1_rejects_past_slot(self):
        self.login("hr@example.test")
        start = utc_now() - timedelta(hours=2)
        end = start + timedelta(minutes=30)
        response = self.post(
            f"/employer/jobs/{self.job}/slots",
            {
                "start_at": start.strftime("%Y-%m-%dT%H:%M"),
                "end_at": end.strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("interview_slots"), 0)

    def test_fp_sched_1_unbooked_slot_can_be_deleted(self):
        slot = self.add_slot(self.employer, self.job)
        self.login("hr@example.test")
        self.assertEqual(self.post(f"/employer/slots/{slot}/delete").status_code, 302)
        self.assertEqual(self.count("interview_slots"), 0)

    def test_fp_sched_1_booked_slot_cannot_be_deleted(self):
        slot = self.add_slot(
            self.employer, self.job, booked_by_application=self.application
        )
        self.login("hr@example.test")
        response = self.post(f"/employer/slots/{slot}/delete")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count("interview_slots"), 1)
        self.assertEqual(self.count("bookings"), 1)

    def test_fp_sched_1_other_employer_cannot_manage_availability(self):
        slot = self.add_slot(self.employer, self.job)
        self.login("other@example.test")
        start, end = self._form_times()
        self.assertEqual(
            self.post(
                f"/employer/jobs/{self.job}/slots", {"start_at": start, "end_at": end}
            ).status_code,
            403,
        )
        self.assertEqual(self.post(f"/employer/slots/{slot}/delete").status_code, 403)
        self.assertEqual(self.count("interview_slots"), 1)

    def test_fp_sched_1_booked_slot_is_not_shown_as_available(self):
        booked = self.add_slot(
            self.employer, self.job, booked_by_application=self.application
        )
        available = self.add_slot(self.employer, self.job)
        self.login("cand@example.test")

        slots = self.call(services.list_available_slots, self.candidate, self.application)
        self.assertEqual([slot["id"] for slot in slots], [])  # application has a booking

        # A second, Interviewing application sees only the unbooked slot.
        second_job = self.add_job(self.employer, "Second Job", "Python")
        application = self.add_application(self.candidate, second_job, "Interviewing")
        slots = self.call(services.list_available_slots, self.candidate, application)
        self.assertEqual([slot["id"] for slot in slots], [available])
        self.assertNotIn(booked, [slot["id"] for slot in slots])


class BookingEligibilityTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.other_employer = self.add_user("other.hr@example.test", "Employer", "Other Co")
        self.job = self.add_job(self.employer)
        self.other_job = self.add_job(self.other_employer, "Other Job", "Go")
        self.candidate = self.add_user("cand@example.test", "Candidate", "Cand")
        self.other_candidate = self.add_user("other@example.test", "Candidate", "Other")
        self.application = self.add_application(self.candidate, self.job, "Interviewing")
        self.slot = self.add_slot(self.employer, self.job)

    def test_fp_sched_2_candidate_books_slot_and_both_sides_see_it(self):
        self.login("cand@example.test")
        response = self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": self.slot}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count("bookings"), 1)

        candidate_page = self.body(self.get("/candidate/applications"))
        self.assertIn("Interview booked", candidate_page)

        self.logout()
        self.login("hr@example.test")
        employer_page = self.body(self.get(f"/employer/jobs/{self.job}/applicants"))
        self.assertIn("Interview", employer_page)
        start_at = self.scalar(
            "SELECT start_at FROM interview_slots WHERE id = ?", (self.slot,)
        )
        end_at = self.scalar(
            "SELECT end_at FROM interview_slots WHERE id = ?", (self.slot,)
        )
        self.assertIn(format_utc(start_at), employer_page)
        self.assertIn(format_utc(end_at), employer_page)

    def test_fp_sched_2_booking_requires_interviewing_status(self):
        self.login("cand@example.test")
        for status in ("Pending", "Rejected", "Accepted"):
            with self.app.app_context():
                from app.db import get_db

                get_db().execute(
                    "UPDATE applications SET status = ? WHERE id = ?",
                    (status, self.application),
                )
            response = self.post(
                f"/candidate/applications/{self.application}/book",
                {"slot_id": self.slot},
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.count("bookings"), 0)

    def test_fp_sched_2_booking_requires_own_application(self):
        self.login("other@example.test")
        response = self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": self.slot}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.count("bookings"), 0)

    def test_fp_sched_2_booking_requires_slot_from_same_employer(self):
        foreign_slot = self.add_slot(self.other_employer, self.other_job)
        self.login("cand@example.test")
        response = self.post(
            f"/candidate/applications/{self.application}/book",
            {"slot_id": foreign_slot},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.count("bookings"), 0)

    def test_fp_sched_2_booking_requires_future_unbooked_slot(self):
        self.login("cand@example.test")
        past_slot = self.add_slot(
            self.employer, self.job, start=utc_now() - timedelta(hours=2)
        )
        response = self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": past_slot}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count("bookings"), 0)

        # Book the slot, then a second application cannot take it.
        self.assertEqual(
            self.post(
                f"/candidate/applications/{self.application}/book",
                {"slot_id": self.slot},
            ).status_code,
            302,
        )
        second_application = self.add_application(
            self.other_candidate, self.job, "Interviewing"
        )
        self.logout()
        self.login("other@example.test")
        response = self.post(
            f"/candidate/applications/{second_application}/book",
            {"slot_id": self.slot},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already booked", self.body(response))
        self.assertEqual(self.count("bookings"), 1)

    def test_fp_sched_2_application_can_have_only_one_booking(self):
        second_slot = self.add_slot(self.employer, self.job)
        self.login("cand@example.test")
        self.assertEqual(
            self.post(
                f"/candidate/applications/{self.application}/book",
                {"slot_id": self.slot},
            ).status_code,
            302,
        )
        response = self.post(
            f"/candidate/applications/{self.application}/book",
            {"slot_id": second_slot},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count("bookings"), 1)

    def test_fp_sched_2_booking_survives_status_change_and_slot_stays_booked(self):
        self.login("cand@example.test")
        self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": self.slot}
        )
        self.logout()
        self.login("hr@example.test")
        self.post(
            f"/employer/applications/{self.application}/status",
            {"status": "Rejected"},
        )

        self.assertEqual(
            self.scalar("SELECT status FROM applications WHERE id = ?", (self.application,)),
            "Rejected",
        )
        self.assertEqual(
            self.scalar("SELECT slot_id FROM bookings WHERE application_id = ?", (self.application,)),
            self.slot,
        )
        self.assertEqual(
            self.call(services.list_available_slots, self.candidate, self.application),
            [],
        )
        # The slot is still unavailable to everyone.
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM bookings WHERE slot_id = ?", (self.slot,)
            ),
            1,
        )

    def test_fp_sched_2_ineligible_booking_changes_nothing(self):
        self.login("cand@example.test")
        response = self.post(
            f"/candidate/applications/{self.application}/book", {"slot_id": 99999}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.count("bookings"), 0)
        self.assertEqual(
            self.scalar("SELECT status FROM applications WHERE id = ?", (self.application,)),
            "Interviewing",
        )


class ConcurrentBookingTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.employer = self.add_user("hr@example.test", "Employer", "Hiring Co")
        self.job = self.add_job(self.employer)
        self.candidate_a = self.add_user("a@example.test", "Candidate", "A")
        self.candidate_b = self.add_user("b@example.test", "Candidate", "B")
        self.application_a = self.add_application(self.candidate_a, self.job, "Interviewing")
        self.application_b = self.add_application(self.candidate_b, self.job, "Interviewing")
        self.slot = self.add_slot(self.employer, self.job)

    def test_fp_sched_3_concurrent_booking_exactly_one_wins(self):
        barrier = threading.Barrier(2)
        results: list[tuple] = []

        def attempt(candidate_id: int, application_id: int) -> None:
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    services.book_slot(candidate_id, application_id, self.slot)
                    results.append(("ok", None))
                except AppError as exc:
                    results.append(("error", exc.status, exc.message))

        threads = [
            threading.Thread(target=attempt, args=(self.candidate_a, self.application_a)),
            threading.Thread(target=attempt, args=(self.candidate_b, self.application_b)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(len(results), 2)
        self.assertEqual(sum(1 for result in results if result[0] == "ok"), 1)
        failures = [result for result in results if result[0] == "error"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][1], 409)
        self.assertEqual(failures[0][2], "Slot already booked")
        self.assertEqual(self.count("bookings"), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(DISTINCT slot_id) FROM bookings"), 1
        )

    def test_fp_sched_3_slot_uniqueness_is_enforced_by_the_database(self):
        # The schema, not only application code, guarantees one booking per slot.
        with self.app.app_context():
            from app.db import get_db

            get_db().execute(
                "INSERT INTO bookings (application_id, slot_id, created_at) "
                "VALUES (?, ?, ?)",
                (self.application_a, self.slot, "2026-01-01T00:00:00Z"),
            )
            with self.assertRaises(Exception) as context:
                get_db().execute(
                    "INSERT INTO bookings (application_id, slot_id, created_at) "
                    "VALUES (?, ?, ?)",
                    (self.application_b, self.slot, "2026-01-01T00:00:00Z"),
                )
            self.assertIn("UNIQUE", str(context.exception).upper())
        self.assertEqual(self.count("bookings"), 1)
