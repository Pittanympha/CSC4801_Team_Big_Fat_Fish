"""Business logic shared by the web routes and the unit tests.

The service layer is the only place that writes business data. Routes deal with
HTTP concerns (forms, redirects, flash messages) and call these functions.
Every database statement uses bound parameters.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import timedelta

from .constants import (
    APPLICATION_STATUSES,
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    ROLES,
    SLOT_MINUTES,
    STATUS_INTERVIEWING,
    STATUS_PENDING,
)
from .db import get_db, transaction
from .errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from .matching import (
    applicant_sort_key,
    calculate_match_score,
    job_sort_key,
    normalize_skills,
)
from .security import hash_password, verify_password
from .timeutil import iso_z, parse_utc, utc_now

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_RESUME_LENGTH = 100_000
MIN_PASSWORD_LENGTH = 8


# ---------------------------------------------------------------------------
# Accounts and profiles
# ---------------------------------------------------------------------------


def get_user(user_id: int) -> dict | None:
    row = get_db().execute(
        "SELECT id, email, role, display_name, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def create_user(email: str, password: str, display_name: str, role: str) -> int:
    """Register one Candidate or Employer account and its empty profile."""
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()
    password = password or ""

    if role not in ROLES:
        raise ValidationError("Choose either Candidate or Employer.")
    if not display_name:
        raise ValidationError("Display name is required.")
    if len(display_name) > 120:
        raise ValidationError("Display name must be 120 characters or fewer.")
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ValidationError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 1024:
        raise ValidationError("Password is too long.")

    password_hash = hash_password(password)
    now = iso_z(utc_now())
    try:
        with transaction() as db:
            cursor = db.execute(
                "INSERT INTO users (email, password_hash, role, display_name, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email, password_hash, role, display_name, now),
            )
            user_id = int(cursor.lastrowid)
            if role == ROLE_CANDIDATE:
                db.execute(
                    "INSERT INTO candidate_profiles (user_id, resume_text) VALUES (?, '')",
                    (user_id,),
                )
            else:
                db.execute(
                    "INSERT INTO employer_profiles (user_id, company_name, description) "
                    "VALUES (?, ?, '')",
                    (user_id, display_name),
                )
    except sqlite3.IntegrityError as exc:  # UNIQUE(email)
        raise ConflictError("An account with this email already exists.") from exc
    return user_id


def authenticate(email: str, password: str) -> dict | None:
    email = (email or "").strip().lower()
    if not email or not password:
        return None
    row = get_db().execute(
        "SELECT id, email, role, display_name, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if row is None:
        return None
    if not verify_password(row["password_hash"], password):
        return None
    return {key: row[key] for key in ("id", "email", "role", "display_name")}


def get_candidate_profile(candidate_id: int) -> dict:
    row = get_db().execute(
        "SELECT u.id, u.display_name, u.email, p.resume_text "
        "FROM users u JOIN candidate_profiles p ON p.user_id = u.id "
        "WHERE u.id = ? AND u.role = ?",
        (candidate_id, ROLE_CANDIDATE),
    ).fetchone()
    if row is None:
        raise NotFoundError("Candidate profile not found.")
    skills = [
        item["skill"]
        for item in get_db().execute(
            "SELECT skill FROM candidate_skills WHERE user_id = ? ORDER BY skill",
            (candidate_id,),
        ).fetchall()
    ]
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "email": row["email"],
        "resume_text": row["resume_text"],
        "skills": skills,
    }


def update_candidate_profile(
    candidate_id: int, display_name: str, skills_raw: str, resume_text: str
) -> None:
    display_name = (display_name or "").strip()
    resume_text = resume_text or ""
    if not display_name:
        raise ValidationError("Display name is required.")
    if len(display_name) > 120:
        raise ValidationError("Display name must be 120 characters or fewer.")
    if len(resume_text) > MAX_RESUME_LENGTH:
        raise ValidationError("Resume is too long.")
    skills = sorted(normalize_skills(skills_raw))

    with transaction() as db:
        db.execute(
            "UPDATE users SET display_name = ? WHERE id = ? AND role = ?",
            (display_name, candidate_id, ROLE_CANDIDATE),
        )
        db.execute(
            "INSERT INTO candidate_profiles (user_id, resume_text) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET resume_text = excluded.resume_text",
            (candidate_id, resume_text),
        )
        db.execute("DELETE FROM candidate_skills WHERE user_id = ?", (candidate_id,))
        db.executemany(
            "INSERT INTO candidate_skills (user_id, skill) VALUES (?, ?)",
            [(candidate_id, skill) for skill in skills],
        )


def get_resume(candidate_id: int) -> str:
    row = get_db().execute(
        "SELECT resume_text FROM candidate_profiles WHERE user_id = ?", (candidate_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Resume not found.")
    return row["resume_text"]


def get_company_profile(employer_id: int) -> dict:
    row = get_db().execute(
        "SELECT u.id, u.display_name, u.email, e.company_name, e.description "
        "FROM users u LEFT JOIN employer_profiles e ON e.user_id = u.id "
        "WHERE u.id = ? AND u.role = ?",
        (employer_id, ROLE_EMPLOYER),
    ).fetchone()
    if row is None:
        raise NotFoundError("Employer profile not found.")
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "email": row["email"],
        "company_name": row["company_name"] or row["display_name"],
        "description": row["description"] or "",
    }


def update_company_profile(employer_id: int, company_name: str, description: str) -> None:
    company_name = (company_name or "").strip()
    description = (description or "").strip()
    if not company_name:
        raise ValidationError("Company name is required.")
    if len(company_name) > 160:
        raise ValidationError("Company name must be 160 characters or fewer.")
    if len(description) > 5_000:
        raise ValidationError("Company description is too long.")
    with transaction() as db:
        db.execute(
            "INSERT INTO employer_profiles (user_id, company_name, description) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "company_name = excluded.company_name, description = excluded.description",
            (employer_id, company_name, description),
        )


# ---------------------------------------------------------------------------
# Queries shared by candidate/employer views
# ---------------------------------------------------------------------------


def _candidate_skills(candidate_id: int) -> set[str]:
    rows = get_db().execute(
        "SELECT skill FROM candidate_skills WHERE user_id = ?", (candidate_id,)
    ).fetchall()
    return {row["skill"] for row in rows}


def _skills_by_job(job_ids: list[int]) -> dict[int, list[str]]:
    if not job_ids:
        return {}
    placeholders = ",".join("?" for _ in job_ids)
    rows = get_db().execute(
        f"SELECT job_id, skill FROM job_skills WHERE job_id IN ({placeholders}) ORDER BY skill",
        tuple(job_ids),
    ).fetchall()
    result: dict[int, list[str]] = {job_id: [] for job_id in job_ids}
    for row in rows:
        result.setdefault(row["job_id"], []).append(row["skill"])
    return result


def _skills_by_candidate(candidate_ids: list[int]) -> dict[int, list[str]]:
    if not candidate_ids:
        return {}
    placeholders = ",".join("?" for _ in candidate_ids)
    rows = get_db().execute(
        f"SELECT user_id, skill FROM candidate_skills "
        f"WHERE user_id IN ({placeholders}) ORDER BY skill",
        tuple(candidate_ids),
    ).fetchall()
    result: dict[int, list[str]] = {cid: [] for cid in candidate_ids}
    for row in rows:
        result.setdefault(row["user_id"], []).append(row["skill"])
    return result


# ---------------------------------------------------------------------------
# Candidate workflow
# ---------------------------------------------------------------------------


def list_recommended_jobs(candidate_id: int) -> list[dict]:
    """All current jobs with their deterministic score, highest first."""
    db = get_db()
    candidate_skills = _candidate_skills(candidate_id)
    rows = db.execute(
        "SELECT j.id, j.title, j.description, j.employer_id, "
        "       COALESCE(NULLIF(e.company_name, ''), u.display_name) AS company_name "
        "FROM jobs j "
        "JOIN users u ON u.id = j.employer_id "
        "LEFT JOIN employer_profiles e ON e.user_id = j.employer_id "
        "ORDER BY j.id"
    ).fetchall()
    skills_map = _skills_by_job([row["id"] for row in rows])
    status_rows = db.execute(
        "SELECT job_id, status FROM applications WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    status_map = {row["job_id"]: row["status"] for row in status_rows}

    jobs = []
    for row in rows:
        required = skills_map.get(row["id"], [])
        jobs.append(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "employer_id": row["employer_id"],
                "company_name": row["company_name"],
                "required_skills": required,
                "score": calculate_match_score(candidate_skills, required),
                "application_status": status_map.get(row["id"]),
            }
        )
    return sorted(jobs, key=job_sort_key)


def get_candidate_job(candidate_id: int, job_id: int) -> dict:
    row = get_db().execute(
        "SELECT j.id, j.title, j.description, j.employer_id, "
        "       COALESCE(NULLIF(e.company_name, ''), u.display_name) AS company_name, "
        "       u.display_name AS employer_name "
        "FROM jobs j JOIN users u ON u.id = j.employer_id "
        "LEFT JOIN employer_profiles e ON e.user_id = j.employer_id "
        "WHERE j.id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Job not found.")
    required = _skills_by_job([job_id]).get(job_id, [])
    application = get_db().execute(
        "SELECT a.id, a.status, b.id AS booking_id, s.start_at, s.end_at "
        "FROM applications a "
        "LEFT JOIN bookings b ON b.application_id = a.id "
        "LEFT JOIN interview_slots s ON s.id = b.slot_id "
        "WHERE a.job_id = ? AND a.candidate_id = ?",
        (job_id, candidate_id),
    ).fetchone()
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "employer_id": row["employer_id"],
        "company_name": row["company_name"],
        "employer_name": row["employer_name"],
        "required_skills": required,
        "score": calculate_match_score(_candidate_skills(candidate_id), required),
        "application": dict(application) if application else None,
    }


def create_application(candidate_id: int, job_id: int) -> int:
    db = get_db()
    job = db.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise NotFoundError("Job not found.")
    try:
        with transaction() as tx:
            cursor = tx.execute(
                "INSERT INTO applications (job_id, candidate_id, status, created_at) "
                "VALUES (?, ?, ?, ?)",
                (job_id, candidate_id, STATUS_PENDING, iso_z(utc_now())),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ConflictError("You have already applied to this job.") from exc


def list_candidate_applications(candidate_id: int) -> list[dict]:
    rows = get_db().execute(
        "SELECT a.id, a.status, a.created_at, "
        "       j.id AS job_id, j.title AS job_title, j.employer_id, "
        "       u.display_name AS employer_name, "
        "       COALESCE(NULLIF(e.company_name, ''), u.display_name) AS company_name, "
        "       b.id AS booking_id, s.start_at, s.end_at "
        "FROM applications a "
        "JOIN jobs j ON j.id = a.job_id "
        "JOIN users u ON u.id = j.employer_id "
        "LEFT JOIN employer_profiles e ON e.user_id = j.employer_id "
        "LEFT JOIN bookings b ON b.application_id = a.id "
        "LEFT JOIN interview_slots s ON s.id = b.slot_id "
        "WHERE a.candidate_id = ? "
        "ORDER BY a.created_at DESC, a.id DESC",
        (candidate_id,),
    ).fetchall()

    applications = []
    for row in rows:
        item = dict(row)
        item["available_slots"] = []
        if item["status"] == STATUS_INTERVIEWING and item["booking_id"] is None:
            item["available_slots"] = _available_slots_for_employer(item["employer_id"])
        applications.append(item)
    return applications


def _available_slots_for_employer(employer_id: int) -> list[dict]:
    rows = get_db().execute(
        "SELECT s.id, s.start_at, s.end_at, j.title AS job_title "
        "FROM interview_slots s JOIN jobs j ON j.id = s.job_id "
        "WHERE s.employer_id = ? AND s.start_at > ? "
        "  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.slot_id = s.id) "
        "ORDER BY s.start_at, s.id",
        (employer_id, iso_z(utc_now())),
    ).fetchall()
    return [dict(row) for row in rows]


def list_available_slots(candidate_id: int, application_id: int) -> list[dict]:
    """Available slots for an application, or an empty list when ineligible."""
    row = get_db().execute(
        "SELECT a.id, a.status, a.candidate_id, j.employer_id, "
        "       (SELECT COUNT(*) FROM bookings b WHERE b.application_id = a.id) AS booking_count "
        "FROM applications a JOIN jobs j ON j.id = a.job_id "
        "WHERE a.id = ?",
        (application_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Application not found.")
    if row["candidate_id"] != candidate_id:
        raise ForbiddenError("You can only manage your own applications.")
    if row["status"] != STATUS_INTERVIEWING or row["booking_count"]:
        return []
    return _available_slots_for_employer(row["employer_id"])


# ---------------------------------------------------------------------------
# Interview scheduling
# ---------------------------------------------------------------------------


def book_slot(candidate_id: int, application_id: int, slot_id: int) -> int:
    """Atomically book a future slot for an eligible application.

    The whole eligibility check and the insert run inside one
    ``BEGIN IMMEDIATE`` transaction. The UNIQUE(slot_id) constraint is the
    final guard: when two eligible candidates race, exactly one insert wins and
    the other receives ``409 Slot already booked``.
    """
    with transaction() as db:
        application = db.execute(
            "SELECT a.id, a.status, a.candidate_id, a.job_id, j.employer_id "
            "FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.id = ?",
            (application_id,),
        ).fetchone()
        if application is None:
            raise NotFoundError("Application not found.")
        if application["candidate_id"] != candidate_id:
            raise ForbiddenError("You can only book with your own application.")
        if application["status"] != STATUS_INTERVIEWING:
            raise ConflictError("Only Interviewing applications can book a slot.")
        if db.execute(
            "SELECT 1 FROM bookings WHERE application_id = ?", (application_id,)
        ).fetchone():
            raise ConflictError("Application already has a booking.")

        slot = db.execute(
            "SELECT id, employer_id, start_at, end_at FROM interview_slots WHERE id = ?",
            (slot_id,),
        ).fetchone()
        if slot is None:
            raise NotFoundError("Interview slot not found.")
        if slot["employer_id"] != application["employer_id"]:
            raise ForbiddenError("The slot does not belong to this application's employer.")
        if slot["start_at"] <= iso_z(utc_now()):
            raise ConflictError("The slot is not in the future.")
        if db.execute("SELECT 1 FROM bookings WHERE slot_id = ?", (slot_id,)).fetchone():
            raise ConflictError("Slot already booked")

        try:
            cursor = db.execute(
                "INSERT INTO bookings (application_id, slot_id, created_at) VALUES (?, ?, ?)",
                (application_id, slot_id, iso_z(utc_now())),
            )
        except sqlite3.IntegrityError as exc:
            # Both UNIQUE(application_id) and UNIQUE(slot_id) land here. The
            # contract-visible race message is fixed by FP-SCHED-3.
            raise ConflictError("Slot already booked") from exc
        return int(cursor.lastrowid)


# ---------------------------------------------------------------------------
# Employer workflow
# ---------------------------------------------------------------------------


def _get_owned_job(employer_id: int, job_id: int) -> dict:
    row = get_db().execute(
        "SELECT j.id, j.employer_id, j.title, j.description, j.created_at, j.updated_at "
        "FROM jobs j WHERE j.id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Job not found.")
    if row["employer_id"] != employer_id:
        raise ForbiddenError("You can only manage your own job postings.")
    return dict(row)


def get_employer_job(employer_id: int, job_id: int) -> dict:
    job = _get_owned_job(employer_id, job_id)
    job["required_skills"] = _skills_by_job([job_id]).get(job_id, [])
    return job


def list_employer_jobs(employer_id: int) -> list[dict]:
    rows = get_db().execute(
        "SELECT j.id, j.title, j.description, j.created_at, j.updated_at, "
        "       (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS application_count, "
        "       (SELECT COUNT(*) FROM interview_slots s WHERE s.job_id = j.id) AS slot_count "
        "FROM jobs j WHERE j.employer_id = ? ORDER BY j.id DESC",
        (employer_id,),
    ).fetchall()
    skills_map = _skills_by_job([row["id"] for row in rows])
    jobs = []
    for row in rows:
        item = dict(row)
        item["required_skills"] = skills_map.get(row["id"], [])
        jobs.append(item)
    return jobs


def save_job(
    employer_id: int,
    job_id: int | None,
    title: str,
    description: str,
    skills_raw: str,
) -> int:
    title = (title or "").strip()
    description = (description or "").strip()
    if not title:
        raise ValidationError("Job title is required.")
    if len(title) > 160:
        raise ValidationError("Job title must be 160 characters or fewer.")
    if not description:
        raise ValidationError("Job description is required.")
    if len(description) > 20_000:
        raise ValidationError("Job description is too long.")
    skills = sorted(normalize_skills(skills_raw))
    now = iso_z(utc_now())

    with transaction() as db:
        if job_id is None:
            cursor = db.execute(
                "INSERT INTO jobs (employer_id, title, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (employer_id, title, description, now, now),
            )
            job_id = int(cursor.lastrowid)
        else:
            owned = db.execute(
                "SELECT employer_id FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if owned is None:
                raise NotFoundError("Job not found.")
            if owned["employer_id"] != employer_id:
                raise ForbiddenError("You can only manage your own job postings.")
            db.execute(
                "UPDATE jobs SET title = ?, description = ?, updated_at = ? WHERE id = ?",
                (title, description, now, job_id),
            )
        db.execute("DELETE FROM job_skills WHERE job_id = ?", (job_id,))
        db.executemany(
            "INSERT INTO job_skills (job_id, skill) VALUES (?, ?)",
            [(job_id, skill) for skill in skills],
        )
    return job_id


def delete_job(employer_id: int, job_id: int) -> None:
    _get_owned_job(employer_id, job_id)
    with transaction() as db:
        application_count = db.execute(
            "SELECT COUNT(*) AS n FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()["n"]
        slot_count = db.execute(
            "SELECT COUNT(*) AS n FROM interview_slots WHERE job_id = ?", (job_id,)
        ).fetchone()["n"]
        if application_count or slot_count:
            raise ConflictError(
                "This job has applications or interview slots and cannot be deleted."
            )
        db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def list_applicants(employer_id: int, job_id: int) -> list[dict]:
    job = _get_owned_job(employer_id, job_id)
    required = _skills_by_job([job_id]).get(job_id, [])
    rows = get_db().execute(
        "SELECT a.id AS application_id, a.status, a.created_at, "
        "       u.id AS candidate_id, u.display_name, u.email, "
        "       b.id AS booking_id, s.start_at, s.end_at "
        "FROM applications a "
        "JOIN users u ON u.id = a.candidate_id "
        "LEFT JOIN bookings b ON b.application_id = a.id "
        "LEFT JOIN interview_slots s ON s.id = b.slot_id "
        "WHERE a.job_id = ?",
        (job_id,),
    ).fetchall()
    skills_map = _skills_by_candidate([row["candidate_id"] for row in rows])
    applicants = []
    for row in rows:
        item = dict(row)
        item["skills"] = skills_map.get(row["candidate_id"], [])
        item["score"] = calculate_match_score(item["skills"], required)
        applicants.append(item)
    return sorted(applicants, key=applicant_sort_key)


def update_application_status(employer_id: int, application_id: int, new_status: str) -> int:
    if new_status not in APPLICATION_STATUSES:
        raise ValidationError("Unknown application status.")
    row = get_db().execute(
        "SELECT a.id, a.job_id, j.employer_id FROM applications a "
        "JOIN jobs j ON j.id = a.job_id WHERE a.id = ?",
        (application_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Application not found.")
    if row["employer_id"] != employer_id:
        raise ForbiddenError("You can only manage applicants for your own jobs.")
    get_db().execute(
        "UPDATE applications SET status = ? WHERE id = ?", (new_status, application_id)
    )
    return int(row["job_id"])


def list_slots(employer_id: int, job_id: int) -> list[dict]:
    _get_owned_job(employer_id, job_id)
    rows = get_db().execute(
        "SELECT s.id, s.start_at, s.end_at, s.created_at, "
        "       b.id AS booking_id, u.display_name AS booked_by "
        "FROM interview_slots s "
        "LEFT JOIN bookings b ON b.slot_id = s.id "
        "LEFT JOIN applications a ON a.id = b.application_id "
        "LEFT JOIN users u ON u.id = a.candidate_id "
        "WHERE s.job_id = ? ORDER BY s.start_at, s.id",
        (job_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def create_slot(employer_id: int, job_id: int, start_raw: str, end_raw: str) -> int:
    job = _get_owned_job(employer_id, job_id)
    try:
        start = parse_utc(start_raw)
        end = parse_utc(end_raw)
    except ValueError as exc:
        raise ValidationError("Enter a valid start and end date/time.") from exc

    now = utc_now()
    if start <= now:
        raise ValidationError("Interview slots must start in the future.")
    if end <= start:
        raise ValidationError("End time must be after the start time.")
    if end - start != timedelta(minutes=SLOT_MINUTES):
        raise ValidationError(f"Interview slots must be exactly {SLOT_MINUTES} minutes long.")

    with transaction() as db:
        cursor = db.execute(
            "INSERT INTO interview_slots (job_id, employer_id, start_at, end_at, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job["id"], employer_id, iso_z(start), iso_z(end), iso_z(now)),
        )
        return int(cursor.lastrowid)


def delete_slot(employer_id: int, slot_id: int) -> int:
    row = get_db().execute(
        "SELECT s.id, s.job_id, j.employer_id FROM interview_slots s "
        "JOIN jobs j ON j.id = s.job_id WHERE s.id = ?",
        (slot_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Interview slot not found.")
    if row["employer_id"] != employer_id:
        raise ForbiddenError("You can only manage availability for your own jobs.")
    with transaction() as db:
        if db.execute("SELECT 1 FROM bookings WHERE slot_id = ?", (slot_id,)).fetchone():
            raise ConflictError("A booked slot cannot be deleted.")
        db.execute("DELETE FROM interview_slots WHERE id = ?", (slot_id,))
    return int(row["job_id"])
