-- TalentBridge schema (migration 001, applied by `python -m app.cli init-db`).
-- All timestamps are ISO-8601 UTC strings, e.g. 2026-11-29T10:00:00Z.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('Candidate', 'Employer')),
    display_name  TEXT    NOT NULL CHECK (length(trim(display_name)) > 0),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    resume_text TEXT    NOT NULL DEFAULT ''
);

-- Skills are stored normalized (trimmed, lower-case, de-duplicated) so the
-- matching function never depends on presentation formatting.
CREATE TABLE IF NOT EXISTS candidate_skills (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill   TEXT    NOT NULL CHECK (length(skill) > 0),
    PRIMARY KEY (user_id, skill)
);

CREATE TABLE IF NOT EXISTS employer_profiles (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    company_name TEXT    NOT NULL DEFAULT '',
    description  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT    NOT NULL CHECK (length(trim(description)) > 0),
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill  TEXT    NOT NULL CHECK (length(skill) > 0),
    PRIMARY KEY (job_id, skill)
);

CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       TEXT    NOT NULL DEFAULT 'Pending'
                 CHECK (status IN ('Pending', 'Interviewing', 'Rejected', 'Accepted')),
    created_at   TEXT    NOT NULL,
    UNIQUE (job_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS interview_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    employer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_at    TEXT    NOT NULL,
    end_at      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- One booking per application and one booking per slot. The UNIQUE(slot_id)
-- constraint is the database-level guarantee required by FP-SCHED-3.
CREATE TABLE IF NOT EXISTS bookings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    slot_id        INTEGER NOT NULL UNIQUE REFERENCES interview_slots(id) ON DELETE CASCADE,
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_employer ON jobs (employer_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_job ON job_skills (job_id);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications (job_id);
CREATE INDEX IF NOT EXISTS idx_applications_candidate ON applications (candidate_id);
CREATE INDEX IF NOT EXISTS idx_slots_job ON interview_slots (job_id);
CREATE INDEX IF NOT EXISTS idx_slots_employer ON interview_slots (employer_id);
