# TalentBridge — CSC4801 Final Project

A locally runnable, full-stack recruiting and candidate-matching platform built
with Flask, server-rendered Jinja templates, and a persistent SQLite relational
database. Candidates see every job ranked by a transparent skill-overlap score,
apply once, and book 30-minute interviews. Employers post jobs, review ranked
applicants, set exactly four application statuses, and publish availability.

The matching contract, authorization rules, booking transaction, and test
evidence are described in [`SPEC.md`](SPEC.md). Every graded requirement is
mapped to implementation files and named unit tests in the table below.

## Quick start

See [`INSTALL.md`](INSTALL.md) for the exact clean-checkout procedure, Docker
commands, environment variables, migrations, and troubleshooting. The short
version:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.cli init-db
python -m app.cli seed
python -m app.cli run          # http://127.0.0.1:8000
```

Run the complete unit-test suite with one non-interactive command:

```bash
python -m unittest discover -s tests -v
```

The command exits non-zero on failure. Each test uses a unique temporary SQLite
database and no third-party service.

## Verification record (Docker, clean checkout)

Reproduced on a clean checkout with Docker Desktop 4.100.1 (engine 29.9.3, WSL 2
backend, base image `python:3.13-slim`):

| Step | Command | Observed result |
|---|---|---|
| Build | `docker build -t talentbridge .` | exit 0; image `talentbridge:latest`, 192 MB |
| Start | `docker run -d --name talentbridge -p 127.0.0.1:8000:8000 -v talentbridge_data:/data talentbridge` | container `Up (healthy)`; the entrypoint runs `init-db` and `seed` on first boot |
| Health | `curl http://127.0.0.1:8000/healthz` | `{"status":"ok"}` |
| Seed state | read `/data/app.db` inside the container | 7 users, 4 jobs, 6 applications, 3 interview slots, 1 booking |
| Tests | `docker exec talentbridge python -m unittest discover -s tests -v` | `Ran 100 tests in 16.201s` — `OK`, exit code 0 |

The image runs the server as the non-root `app` user, keeps `/data` as the only
writable volume, and declares a `HEALTHCHECK` against `/healthz`. To restore the
deterministic demo state after a walkthrough:

```bash
docker exec talentbridge python -m app.cli seed
```

## Architecture summary

- **Browser UI** — server-rendered HTML and one local CSS file; no JavaScript
  framework, no build step, no external assets.
- **Backend** — Flask application factory with three blueprints (`auth`,
  `candidates`, `employers`). All business rules live in `app/services.py` and
  `app/matching.py`; routes only handle HTTP concerns.
- **Database** — SQLite with foreign keys, CHECK constraints, WAL journal, and
  `BEGIN IMMEDIATE` transactions. Schema: `app/schema.sql` (migration 001).
- **Matching** — one deterministic function used by both candidate and employer
  views: normalized skill-set overlap, with documented tie-breaking.
- **Booking** — one transaction plus `UNIQUE(bookings.slot_id)`; a race produces
  exactly one booking and one `409 Slot already booked`.
- **Security** — scrypt password hashes, signed HttpOnly session cookie, role and
  ownership checks on the server, parameterized SQL, Jinja autoescaping.
- **Tests** — 100 standard-library `unittest` tests covering every functional
  requirement, the 401/403/404 contract, SQL injection, XSS, and two-thread
  booking concurrency.

## Demo accounts (local only)

Run `python -m app.cli seed` first. All accounts below use the password
`DemoPass123!`.

| Email | Role | What it demonstrates |
|---|---|---|
| `alice@demo.test` | Candidate | Python + SQL; `Interviewing` with a booked interview |
| `bob@demo.test` | Candidate | Python only; `Pending` application (50% match) |
| `carol@demo.test` | Candidate | Rust; `Accepted` application on the Rust role |
| `dave@demo.test` | Candidate | `Interviewing`, no booking — race candidate |
| `erin@demo.test` | Candidate | `Interviewing`, no booking — race candidate |
| `hr@acme.test` | Employer | Acme Robotics; 3 jobs, applicants, slots |
| `hr@globex.test` | Employer | Globex Analytics; 1 job |

These are fictional `.test` accounts with a clearly marked demo password. They
must never be used as production credentials.

## Document index

| Document | Purpose |
|---|---|
| [`SPEC.md`](SPEC.md) | Architecture, data model, auth design, routes, screens, matching, booking transaction, security controls |
| [`INSTALL.md`](INSTALL.md) | Prerequisites, install, database, seed, run, test, Docker, troubleshooting |
| [`TEAM.md`](TEAM.md) | Team members, ownership areas, presentation responsibilities |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | Pre-submission and audit-window checklist |
| [`PEER_REVIEW_PLAYBOOK.md`](PEER_REVIEW_PLAYBOOK.md) | How the team audits another repository safely and files findings |
| [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | Ten-minute presentation and live demonstration sequence |
| [`.env.example`](.env.example) | Placeholder-only environment template |
| [`Dockerfile`](Dockerfile) | Complete runnable environment |
| [`.github/ISSUE_TEMPLATE/audit_bug_report.yml`](.github/ISSUE_TEMPLATE/audit_bug_report.yml) | Required audit Issue Form |
| [`.github/labels.yml`](.github/labels.yml) | Required audit label set |

## Requirement–test mapping

All paths are relative to the repository root. Test names are defined in
`tests/test_*.py` and are run by the single command above. `N/A` marks an
optional requirement that is intentionally not implemented.

| Requirement | Implementation | Named unit tests / verification evidence |
|---|---|---|
| **FP-ARCH-1** full-stack boundary | `app/__init__.py`, `app/schema.sql`, `app/templates/`, `run.py`, `Dockerfile` | `test_public_pages_and_health_endpoint_render`, `test_candidate_pages_render`, `test_employer_pages_render`; Docker smoke test in INSTALL §7 |
| **FP-AUTH-1** accounts, two roles, login/logout, unique identifiers | `app/auth.py`, `app/services.py` (`create_user`, `authenticate`), `app/security.py` | `test_fp_auth_1_candidate_register_login_logout`, `test_fp_auth_1_employer_register_creates_company_profile`, `test_fp_auth_1_email_is_unique_case_insensitively`, `test_fp_auth_1_only_two_roles_are_accepted`, `test_fp_auth_1_bad_login_returns_401` |
| **FP-AUTH-2** credential storage and non-disclosure | `app/security.py` (`hash_password`, `verify_password`), `app/services.py` (`create_user`, `authenticate`) | `test_fp_auth_2_passwords_are_hashed_and_never_rendered`, `test_fp_auth_2_short_password_is_rejected` |
| **FP-AUTH-3** server-side 401/403/404 | `app/security.py` (`login_required`, `current_user`), `app/errors.py`, ownership checks in `app/services.py` | `test_fp_auth_3_unauthenticated_get_redirects_to_login`, `test_fp_auth_3_unauthenticated_post_returns_401`, `test_fp_auth_3_wrong_role_returns_403`, `test_fp_auth_3_missing_object_returns_404`, `test_fp_auth_3_other_candidates_resume_returns_403`, `test_fp_auth_3_other_employers_job_returns_403`, `test_fp_auth_3_session_role_cannot_be_forged` |
| **FP-CAN-1** candidate profile, skills, private resume | `app/candidates.py`, `app/services.py` (`update_candidate_profile`, `get_candidate_profile`, `get_resume`), `app/templates/candidate/` | `test_fp_can_1_candidate_edits_own_profile_and_normalized_skills`, `test_fp_can_1_profile_update_only_changes_the_signed_in_candidate`, `test_fp_can_1_empty_display_name_is_rejected_without_saving`, `test_fp_can_1_resume_owner_can_view_and_replace_it`, `test_fp_can_1_other_candidate_and_employer_cannot_read_resume`, `test_fp_can_1_resume_text_is_not_used_for_matching` |
| **FP-CAN-2** ranked job recommendations | `app/services.py` (`list_recommended_jobs`), `app/matching.py`, `app/templates/candidate/dashboard.html` | `test_fp_can_2_dashboard_lists_jobs_with_score_and_fields`, `test_fp_can_2_dashboard_sorted_highest_score_first`, `test_fp_can_2_job_detail_shows_description` |
| **FP-CAN-3** applications once, Pending, privacy, no status changes | `app/candidates.py`, `app/services.py` (`create_application`, `list_candidate_applications`) | `test_fp_can_3_apply_creates_pending_application_once`, `test_fp_can_3_candidate_sees_only_own_applications`, `test_fp_can_3_applications_show_job_company_status_and_booking`, `test_fp_can_3_candidate_cannot_change_application_status`, `test_fp_can_3_candidate_cannot_view_another_candidates_application_data` |
| **FP-EMP-1** company profile | `app/employers.py` (`company`), `app/services.py` (`get_company_profile`, `update_company_profile`) | `test_fp_emp_1_employer_views_and_edits_company_profile`, `test_fp_emp_1_empty_company_name_is_rejected` |
| **FP-EMP-2** job CRUD, ownership, delete conflicts | `app/employers.py` (`job_new`, `job_edit`, `job_delete`), `app/services.py` (`save_job`, `delete_job`) | `test_fp_emp_2_create_read_update_delete_own_job`, `test_fp_emp_2_job_requires_title_and_description`, `test_fp_emp_2_other_employer_cannot_edit_or_delete_job`, `test_fp_emp_2_delete_job_with_application_returns_409`, `test_fp_emp_2_delete_job_with_slot_returns_409`, `test_fp_emp_2_job_without_dependents_is_deletable` |
| **FP-EMP-3** applicant management and four statuses | `app/employers.py` (`applicants`, `application_status`), `app/services.py` (`list_applicants`, `update_application_status`) | `test_fp_emp_3_applicants_sorted_with_identity_skills_score_status`, `test_fp_emp_3_all_four_statuses_can_be_set`, `test_fp_emp_3_invalid_status_is_rejected`, `test_fp_emp_3_other_employer_cannot_view_or_change_applicants`, `test_fp_emp_3_candidate_cannot_change_status`, `test_fp_emp_3_applicant_list_does_not_expose_resumes` |
| **FP-MATCH-1** deterministic score and tie-breaks | `app/matching.py`; used by `app/services.py` (`list_recommended_jobs`, `list_applicants`); seed in `app/seed.py` | `test_fp_match_1_required_examples`, `test_fp_match_1_normalizes_whitespace_case_and_duplicates`, `test_fp_match_1_empty_required_set_scores_one_hundred`, `test_fp_match_1_score_is_integer_floor_between_0_and_100`, `test_fp_match_1_candidate_dashboard_sorts_score_title_then_id`, `test_fp_match_1_employer_applicants_sort_score_name_then_id`, `test_fp_match_1_same_score_in_candidate_and_employer_views` |
| **FP-MATCH-2** optional AI enhancement | Not implemented | `N/A` — no LLM call, no API key, no effect on score or ordering |
| **FP-SCHED-1** availability rules | `app/employers.py` (`job_slots`, `slot_delete`), `app/services.py` (`create_slot`, `delete_slot`, `list_slots`), `app/timeutil.py` | `test_fp_sched_1_employer_creates_thirty_minute_future_slot`, `test_fp_sched_1_rejects_non_thirty_minute_duration`, `test_fp_sched_1_rejects_end_before_start`, `test_fp_sched_1_rejects_past_slot`, `test_fp_sched_1_unbooked_slot_can_be_deleted`, `test_fp_sched_1_booked_slot_cannot_be_deleted`, `test_fp_sched_1_other_employer_cannot_manage_availability`, `test_fp_sched_1_booked_slot_is_not_shown_as_available` |
| **FP-SCHED-2** booking eligibility and lifecycle | `app/services.py` (`book_slot`, `list_available_slots`), `app/candidates.py` (`book`), booking views | `test_fp_sched_2_candidate_books_slot_and_both_sides_see_it`, `test_fp_sched_2_booking_requires_interviewing_status`, `test_fp_sched_2_booking_requires_own_application`, `test_fp_sched_2_booking_requires_slot_from_same_employer`, `test_fp_sched_2_booking_requires_future_unbooked_slot`, `test_fp_sched_2_application_can_have_only_one_booking`, `test_fp_sched_2_booking_survives_status_change_and_slot_stays_booked`, `test_fp_sched_2_ineligible_booking_changes_nothing` |
| **FP-SCHED-3** atomic concurrent booking | `app/db.py` (`transaction` with `BEGIN IMMEDIATE`), `app/services.py` (`book_slot`), `app/schema.sql` (`UNIQUE(bookings.slot_id)`, `UNIQUE(bookings.application_id)`) | `test_fp_sched_3_concurrent_booking_exactly_one_wins`, `test_fp_sched_3_slot_uniqueness_is_enforced_by_the_database` |
| **FP-SEC-1** object-access boundaries | `app/security.py`, ownership checks in `app/services.py`, private resume route | `test_fp_sec_1_candidate_cannot_read_or_modify_another_candidates_data`, `test_fp_sec_1_employer_cannot_modify_another_job_or_read_applicants`, `test_fp_sec_1_candidate_cannot_book_with_another_candidates_application` |
| **FP-SEC-2** SQL injection prevention | `app/db.py`, all SQL in `app/services.py`, `app/seed.py` uses bound parameters | `test_fp_sec_2_sql_injection_in_login_cannot_bypass_authentication`, `test_fp_sec_2_sql_metacharacters_are_bound_not_executed`, `test_fp_sec_2_sql_metacharacters_in_job_text_are_bound` |
| **FP-SEC-3** XSS escaping | Jinja autoescape in `app/templates/`, no `\|safe`; escaped rendering of profile, resume, company, and job text | `test_fp_sec_3_profile_display_name_is_escaped`, `test_fp_sec_3_resume_text_is_escaped`, `test_fp_sec_3_job_and_company_text_is_escaped` |
| **FP-SEC-4** secrets and test isolation | `.env.example`, `.gitignore`, `tests/support.py` isolated temporary DBs, no network calls in tests | `test_fp_sec_4_env_example_contains_placeholders_only`, `test_fp_sec_4_no_env_file_is_committed`, `test_fp_sec_4_tests_use_an_isolated_database`, `test_fp_sec_4_no_obvious_production_secret_in_source` |
| **FP-PROC-1** living specification | `SPEC.md` (architecture, data model, auth, routes, UI screens, matching, booking transaction, security) | `test_fp_proc_1_spec_covers_architecture_data_auth_routes_matching_booking_security`, plus this mapping table |
| **FP-DOC-1** installation documentation | `INSTALL.md`, `Dockerfile`, `docker-entrypoint.sh`, `.env.example` | `test_fp_doc_1_install_documents_build_run_seed_and_test`; clean-checkout checklist in INSTALL §9 |
| **FP-DOC-2** README and requirement mapping | `README.md` (this file), demo accounts, document index, limitations | `test_fp_doc_2_readme_maps_every_requirement_id`, `test_fp_doc_2_every_mapped_test_name_exists`, `test_fp_doc_2_readme_has_demo_credentials_and_test_command` |
| **FP-DOC-3** deterministic seed data | `app/seed.py`, `app/cli.py` (`seed`) | `test_fp_doc_3_seed_has_required_users_jobs_and_applications`, `test_fp_doc_3_seed_covers_all_four_application_statuses`, `test_fp_doc_3_seed_contains_the_four_matching_examples`, `test_fp_doc_3_seed_has_two_interviewing_candidates_racing_for_one_slot`, `test_fp_doc_3_seed_accounts_are_documented_demo_credentials`, `test_fp_doc_3_seed_is_idempotent_and_deterministic` |
| **FP-TEST-1** automated verification | `tests/` (`test_auth`, `test_candidate`, `test_employer`, `test_matching`, `test_scheduling`, `test_security`, `test_seed`, `test_ui`, `test_docs`) | `test_fp_test_1_documented_test_command_runs_suite`; the suite itself is the evidence |
| **FP-SUB-1** submission protocol | `Dockerfile`, `SUBMISSION_CHECKLIST.md`, public `main` commit | `test_fp_sub_1_dockerfile_and_submission_checklist_present`; manual commit-URL check in SUBMISSION_CHECKLIST |

## Known limitations

- **No CSRF tokens.** Session cookies are `SameSite=Lax` and the app is a local
  demo; a production deployment should add synchronizer tokens.
- **Development server.** `python -m app.cli run` / `run.py` use Flask's threaded
  development server, which is appropriate for local grading but not public
  hosting.
- **SQLite single writer.** Booking correctness relies on transactions and
  uniqueness constraints, not on a separate database server. This is sufficient
  for the course's local scale.
- **No pagination or search.** Dashboards render all jobs/applicants; seed data
  is small.
- **No PDF resume upload/extraction.** Plain-text resume is the implemented
  option in FP-CAN-1.
- **No LLM feature.** FP-MATCH-2 is optional and marked `N/A`; no paid
  credentials or network calls exist.
- **No email verification, password reset, OAuth, or notifications.**
- **Audit materials** (issue form and labels) are present, but filing findings
  happens on the target team's public repository during the audit window.

## Team responsibilities

Team composition, ownership areas, and presentation assignments are recorded in
[`TEAM.md`](TEAM.md). Every member must be able to explain and safely modify the
submitted code, including AI-assisted portions.
