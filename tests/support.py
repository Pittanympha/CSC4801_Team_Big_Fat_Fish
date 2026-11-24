"""Shared fixtures for the unit-test suite.

Every test gets its own temporary SQLite database, so tests never touch the
developer database and never call a third-party service (FP-SEC-4).
"""

from __future__ import annotations

import shutil
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app, services
from app.db import get_db, init_db
from app.timeutil import iso_z, utc_now

DEFAULT_PASSWORD = "Password123!"
# Keep test databases inside the workspace: the harness sandbox may deny writes
# to the shared system temp directory on Windows. Each test gets a unique
# directory created with plain os.makedirs (some sandboxes reject tempfile's
# restrictive directory ACLs).
TEST_TMP_ROOT = Path(__file__).resolve().parent.parent / "instance" / "test-tmp"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)

# Hashing is deliberately expensive; reuse one hash for fixture users and keep
# one real service-created user in the password-storage test.
FIXTURE_HASH = generate_password_hash(DEFAULT_PASSWORD, method="scrypt")


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._test_dir = TEST_TMP_ROOT / f"t-{uuid.uuid4().hex}"
        self._test_dir.mkdir(parents=True, exist_ok=False)
        self.db_path = str(self._test_dir / "test.db")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE_PATH": self.db_path,
            }
        )
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        shutil.rmtree(self._test_dir, ignore_errors=True)

    # -- context helpers ---------------------------------------------------
    def call(self, func, *args, **kwargs):
        """Run a service function inside a fresh application context."""
        with self.app.app_context():
            return func(*args, **kwargs)

    def execute(self, sql: str, params=()):
        with self.app.app_context():
            cursor = get_db().execute(sql, params)
            return cursor.lastrowid

    def fetchone(self, sql: str, params=()):
        with self.app.app_context():
            row = get_db().execute(sql, params).fetchone()
            return dict(row) if row is not None else None

    # -- fixture helpers ---------------------------------------------------
    def add_user(
        self,
        email: str,
        role: str = "Candidate",
        display_name: str | None = None,
        password: str = DEFAULT_PASSWORD,
    ) -> int:
        name = display_name or email.split("@")[0].title()
        password_hash = (
            FIXTURE_HASH
            if password == DEFAULT_PASSWORD
            else generate_password_hash(password, method="scrypt")
        )
        with self.app.app_context():
            cursor = get_db().execute(
                "INSERT INTO users (email, password_hash, role, display_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email.lower(), password_hash, role, name, iso_z(utc_now())),
            )
            user_id = int(cursor.lastrowid)
            if role == "Candidate":
                get_db().execute(
                    "INSERT INTO candidate_profiles (user_id, resume_text) VALUES (?, '')",
                    (user_id,),
                )
            else:
                get_db().execute(
                    "INSERT INTO employer_profiles (user_id, company_name, description) "
                    "VALUES (?, ?, '')",
                    (user_id, name),
                )
        return user_id

    def add_job(
        self,
        employer_id: int,
        title: str = "Backend Engineer",
        skills: str = "Python, SQL",
        description: str = "Build services.",
    ) -> int:
        return self.call(services.save_job, employer_id, None, title, description, skills)

    def add_application(
        self, candidate_id: int, job_id: int, status: str = "Pending"
    ) -> int:
        cursor = self.execute(
            "INSERT INTO applications (job_id, candidate_id, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (job_id, candidate_id, status, iso_z(utc_now())),
        )
        return int(cursor)

    def add_slot(
        self,
        employer_id: int,
        job_id: int,
        start=None,
        minutes: int = 30,
        booked_by_application: int | None = None,
    ) -> int:
        start = start or (utc_now() + timedelta(hours=2))
        end = start + timedelta(minutes=minutes)
        slot_id = int(
            self.execute(
                "INSERT INTO interview_slots (job_id, employer_id, start_at, end_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, employer_id, iso_z(start), iso_z(end), iso_z(utc_now())),
            )
        )
        if booked_by_application is not None:
            self.execute(
                "INSERT INTO bookings (application_id, slot_id, created_at) VALUES (?, ?, ?)",
                (booked_by_application, slot_id, iso_z(utc_now())),
            )
        return slot_id

    def login(self, email: str, password: str = DEFAULT_PASSWORD, expect: int = 302):
        response = self.client.post(
            "/login", data={"email": email, "password": password}
        )
        if expect is not None:
            self.assertEqual(response.status_code, expect)
        return response

    def logout(self) -> None:
        self.client.post("/logout")

    def post(self, path: str, data: dict | None = None):
        return self.client.post(path, data=data or {})

    def get(self, path: str):
        return self.client.get(path)

    def body(self, response) -> str:
        return response.get_data(as_text=True)

    def count(self, table: str) -> int:
        return self.fetchone(f"SELECT COUNT(*) AS n FROM {table}")["n"]

    def scalar(self, sql: str, params=()):
        row = self.fetchone(sql, params)
        return next(iter(row.values())) if row else None
