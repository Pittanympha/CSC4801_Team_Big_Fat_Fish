# Team

> This team has two members. 戚正龙 implemented the application; 林屹 built the
> container and the repository, prepared the submission materials, and owns the
> test evidence and documentation consistency. Both members can run the
> clean-checkout flow and explain the whole system.

| Member | Student ID | Primary ownership | Presentation section |
|---|---|---|---|
| 戚正龙 | `123090451` | Application implementation: backend services, database schema, authentication/authorization, matching, booking transaction, templates, unit tests | Problem, architecture, candidate and employer flows, matching formula, booking transaction |
| 林屹 | `123090338` | Delivery and verification: Docker environment, clean-checkout reproduction and test evidence, repository and submission protocol, documentation consistency and requirement mapping, audit coordination | Verification evidence (100 tests, Docker run), security controls, audit and repair process |

## Shared responsibilities

- **Every member can explain and safely modify every part of the submitted
  code**, including AI-generated sections. Ownership above is about primary
  responsibility, not exclusive knowledge.
- **No direct pushes of untested code to `main`** after feature freeze; only bug
  fixes and documentation corrections, reviewed by at least one other member.
- **Requirement traceability is a team artifact.** When a requirement changes,
  update `SPEC.md`, the tests, and the README mapping table in the same commit.
- **Demo rehearsal.** Every member can run the clean-checkout flow in
  `INSTALL.md` and the smoke test in `SUBMISSION_CHECKLIST.md` without help.

## Presentation plan (about 10 minutes)

The demo runs from `DEMO_SCRIPT.md`; the order below is fixed, the time spent on
each section is not.

| # | Section | Speaker |
|---|---|---|
| 1 | Problem and product boundary | 戚正龙 |
| 2 | Architecture and data model | 戚正龙 |
| 3 | Candidate flow: scored recommendations, apply once, private resume | 戚正龙 |
| 4 | Employer flow: ranked applicants, status changes, availability | 戚正龙 |
| 5 | Matching formula and tie-breaking, with the three table examples | 戚正龙 |
| 6 | Booking eligibility and the two-thread race: `BEGIN IMMEDIATE` and `UNIQUE(slot_id)` | 戚正龙 |
| 7 | Verification and security evidence: 100 tests, clean Docker build, resume `403`, SQL-injection and XSS checks | 林屹 |
| 8 | Requirement mapping, known limitations, audit readiness, close | 林屹 |
| Q&A | Each member answers questions about their area and at least one cross-area question | Both |

## Code-review rotation

| Week | Reviewer focus |
|---|---|
| Build weeks | Each change reviewed by the other member for authorization and SQL safety |
| Before feature freeze | Full read-through of `app/services.py` by both members; run the suite on a clean clone |
| Audit window | One member triages and reproduces reports, the other writes the regression test and fix |
