"""Deterministic, local-only demo data (FP-DOC-3).

All accounts, companies, and jobs are fictional and use the reserved ``.test``
domain. The password is a documented demo credential, never a real secret.
The seed is idempotent: running it again resets the data to this exact state.
"""

from __future__ import annotations

from datetime import timedelta

from .constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATUS_ACCEPTED,
    STATUS_INTERVIEWING,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from .db import get_db, transaction
from .matching import normalize_skills
from .security import hash_password
from .timeutil import iso_z, utc_now

DEMO_PASSWORD = "DemoPass123!"

DEMO_ACCOUNTS = [
    {
        "email": "alice@demo.test",
        "name": "Alice Chen",
        "role": ROLE_CANDIDATE,
        "description": "Candidate with Python + SQL, Interviewing and booked.",
    },
    {
        "email": "bob@demo.test",
        "name": "Bob Liu",
        "role": ROLE_CANDIDATE,
        "description": "Candidate with Python only, Pending application.",
    },
    {
        "email": "carol@demo.test",
        "name": "Carol Wang",
        "role": ROLE_CANDIDATE,
        "description": "Candidate with Rust, Accepted application.",
    },
    {
        "email": "dave@demo.test",
        "name": "Dave Zhang",
        "role": ROLE_CANDIDATE,
        "description": "Interviewing candidate eligible for the race slot.",
    },
    {
        "email": "erin@demo.test",
        "name": "Erin Li",
        "role": ROLE_CANDIDATE,
        "description": "Interviewing candidate eligible for the race slot.",
    },
    {
        "email": "hr@acme.test",
        "name": "Acme Recruiter",
        "role": ROLE_EMPLOYER,
        "description": "Employer account for Acme Robotics.",
    },
    {
        "email": "hr@globex.test",
        "name": "Globex Recruiter",
        "role": ROLE_EMPLOYER,
        "description": "Employer account for Globex Analytics.",
    },
]

_DEMO_HASH = hash_password(DEMO_PASSWORD)

_TABLES_IN_DELETE_ORDER = (
    "bookings",
    "interview_slots",
    "applications",
    "job_skills",
    "jobs",
    "candidate_skills",
    "candidate_profiles",
    "employer_profiles",
    "users",
)


def _reset(db) -> None:
    for table in _TABLES_IN_DELETE_ORDER:
        db.execute(f"DELETE FROM {table}")
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone():
        db.execute("DELETE FROM sqlite_sequence")


def _insert_user(db, email: str, name: str, role: str, now: str) -> int:
    cursor = db.execute(
        "INSERT INTO users (email, password_hash, role, display_name, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (email, _DEMO_HASH, role, name, now),
    )
    user_id = int(cursor.lastrowid)
    if role == ROLE_CANDIDATE:
        db.execute(
            "INSERT INTO candidate_profiles (user_id, resume_text) VALUES (?, ?)",
            (user_id, ""),
        )
    else:
        db.execute(
            "INSERT INTO employer_profiles (user_id, company_name, description) VALUES (?, ?, '')",
            (user_id, name),
        )
    return user_id


def _set_skills(db, table: str, column: str, owner_id: int, skills: list[str]) -> None:
    for skill in sorted(normalize_skills(skills)):
        db.execute(
            f"INSERT INTO {table} ({column}, skill) VALUES (?, ?)", (owner_id, skill)
        )


def _insert_job(db, employer_id: int, title: str, description: str, skills: list[str], now: str) -> int:
    cursor = db.execute(
        "INSERT INTO jobs (employer_id, title, description, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (employer_id, title, description, now, now),
    )
    job_id = int(cursor.lastrowid)
    _set_skills(db, "job_skills", "job_id", job_id, skills)
    return job_id


def _insert_application(db, job_id: int, candidate_id: int, status: str, now: str) -> int:
    cursor = db.execute(
        "INSERT INTO applications (job_id, candidate_id, status, created_at) VALUES (?, ?, ?, ?)",
        (job_id, candidate_id, status, now),
    )
    return int(cursor.lastrowid)


def _insert_slot(db, job_id: int, employer_id: int, start, now: str) -> int:
    end = start + timedelta(minutes=30)
    cursor = db.execute(
        "INSERT INTO interview_slots (job_id, employer_id, start_at, end_at, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (job_id, employer_id, iso_z(start), iso_z(end), now),
    )
    return int(cursor.lastrowid)


def seed_database(reset: bool = True) -> dict:
    """Reset (by default) and insert the deterministic demo data set."""
    db = get_db()
    now_dt = utc_now()
    now = iso_z(now_dt)

    # Slots are always in the future, independent of when the seed runs.
    race_start = (now_dt + timedelta(days=3)).replace(hour=10, minute=0, second=0)
    booked_start = race_start + timedelta(hours=1)
    globex_start = (now_dt + timedelta(days=4)).replace(hour=9, minute=0, second=0)

    with transaction() as tx:
        if reset:
            _reset(tx)

        alice = _insert_user(tx, "alice@demo.test", "Alice Chen", ROLE_CANDIDATE, now)
        bob = _insert_user(tx, "bob@demo.test", "Bob Liu", ROLE_CANDIDATE, now)
        carol = _insert_user(tx, "carol@demo.test", "Carol Wang", ROLE_CANDIDATE, now)
        dave = _insert_user(tx, "dave@demo.test", "Dave Zhang", ROLE_CANDIDATE, now)
        erin = _insert_user(tx, "erin@demo.test", "Erin Li", ROLE_CANDIDATE, now)
        acme = _insert_user(tx, "hr@acme.test", "Acme Recruiter", ROLE_EMPLOYER, now)
        globex = _insert_user(tx, "hr@globex.test", "Globex Recruiter", ROLE_EMPLOYER, now)

        tx.execute(
            "UPDATE employer_profiles SET company_name = ?, description = ? WHERE user_id = ?",
            (
                "Acme Robotics",
                "Acme Robotics builds warehouse automation. We hire backend and systems engineers.",
                acme,
            ),
        )
        tx.execute(
            "UPDATE employer_profiles SET company_name = ?, description = ? WHERE user_id = ?",
            (
                "Globex Analytics",
                "Globex Analytics turns operational data into decisions for logistics teams.",
                globex,
            ),
        )

        _set_skills(tx, "candidate_skills", "user_id", alice, ["Python", "SQL"])
        _set_skills(tx, "candidate_skills", "user_id", bob, ["Python"])
        _set_skills(tx, "candidate_skills", "user_id", carol, ["Rust"])
        _set_skills(tx, "candidate_skills", "user_id", dave, ["Python", "SQL"])
        _set_skills(tx, "candidate_skills", "user_id", erin, ["Python", "SQL"])

        tx.execute(
            "UPDATE candidate_profiles SET resume_text = ? WHERE user_id = ?",
            (
                "Alice Chen\nBackend engineer with 4 years of Python and SQL experience.\n"
                "Built payment reconciliation services and query optimizations.",
                alice,
            ),
        )
        tx.execute(
            "UPDATE candidate_profiles SET resume_text = ? WHERE user_id = ?",
            ("Bob Liu\nJunior developer focused on Python automation and testing.", bob),
        )
        tx.execute(
            "UPDATE candidate_profiles SET resume_text = ? WHERE user_id = ?",
            ("Carol Wang\nSystems programmer working in Rust and embedded tooling.", carol),
        )

        backend_job = _insert_job(
            tx,
            acme,
            "Backend Engineer",
            "Design and ship Python services that orchestrate warehouse robots. "
            "You will own APIs, SQL data models, and reliability.",
            ["Python", "SQL"],
            now,
        )
        rust_job = _insert_job(
            tx,
            acme,
            "Rust Systems Engineer",
            "Build low-latency device control software in Rust and improve our "
            "embedded deployment pipeline.",
            ["Rust"],
            now,
        )
        generalist_job = _insert_job(
            tx,
            acme,
            "Junior Generalist",
            "Rotate across product, data, and operations. No specific language "
            "requirement; we value curiosity and clear writing.",
            [],
            now,
        )
        globex_job = _insert_job(
            tx,
            globex,
            "Data Analyst",
            "Own reporting for logistics customers: SQL models, dashboards, and "
            "weekly insight reviews with account teams.",
            ["Python", "SQL"],
            now,
        )

        # Applications cover all four statuses.
        alice_app = _insert_application(tx, backend_job, alice, STATUS_INTERVIEWING, now)
        _insert_application(tx, backend_job, bob, STATUS_PENDING, now)
        _insert_application(tx, rust_job, carol, STATUS_ACCEPTED, now)
        _insert_application(tx, rust_job, dave, STATUS_REJECTED, now)
        dave_app = _insert_application(tx, backend_job, dave, STATUS_INTERVIEWING, now)
        erin_app = _insert_application(tx, backend_job, erin, STATUS_INTERVIEWING, now)

        # One unbooked slot for Dave and Erin to race for, one booked slot for Alice.
        race_slot = _insert_slot(tx, backend_job, acme, race_start, now)
        booked_slot = _insert_slot(tx, backend_job, acme, booked_start, now)
        _insert_slot(tx, globex_job, globex, globex_start, now)
        tx.execute(
            "INSERT INTO bookings (application_id, slot_id, created_at) VALUES (?, ?, ?)",
            (alice_app, booked_slot, now),
        )

    return {
        "users": 7,
        "jobs": 4,
        "applications": 6,
        "slots": 3,
        "bookings": 1,
        "race_slot_id": race_slot,
        "race_candidates": {"dave": dave_app, "erin": erin_app},
        "backend_job_id": backend_job,
        "alice_id": alice,
        "bob_id": bob,
        "carol_id": carol,
    }
