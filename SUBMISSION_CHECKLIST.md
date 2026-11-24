# Submission checklist

Deadlines and exact dates are published on the course site. The intro deck lists
the initial submission at **Week 11 (Nov 26)** and the audit at **Week 12**;
treat the course site as authoritative.

## 1. Repository and commit

- [ ] The repository is **public** and stays public through the audit window.
- [ ] All work is committed on **`main`**; the graded commit is pushed before the
      deadline.
- [ ] The commit is permanent (not amended or force-pushed after submission).
- [ ] The submission URL has the exact form
      `https://github.com/<owner>/<repository>/commit/<40-character-sha>`.
      A `/tree/main` branch URL is **not** accepted.
- [ ] `git rev-parse HEAD` on a fresh clone equals the 40-character SHA in the
      submitted URL.
- [ ] No `.env`, database file, credential, API key, or personal data is
      committed (`git ls-files | findstr /i ".env"` on Windows, `git ls-files |
      grep -i '\.env'` elsewhere; `instance/` is ignored).

## 2. Clean-checkout build

On a machine or fresh clone without cached state:

- [ ] `docker build -t talentbridge .` succeeds with no undocumented command or
      secret.
- [ ] `docker run -d --name talentbridge -p 127.0.0.1:8000:8000 -v talentbridge_data:/data talentbridge`
      starts the server.
- [ ] `curl http://127.0.0.1:8000/healthz` returns `{"status":"ok"}`.
- [ ] `docker exec talentbridge python -m app.cli init-db` succeeds.
- [ ] `docker exec talentbridge python -m app.cli seed` resets the deterministic
      data.
- [ ] `docker exec talentbridge python -m unittest discover -s tests -v` ends
      with `OK` and exit code 0.
- [ ] The browser smoke test below passes inside the container.

## 3. Browser smoke test

- [ ] Landing page loads; register a candidate and an employer.
- [ ] Candidate profile saves a display name, skills, and resume; resume is not
      visible to another candidate or employer (`403`).
- [ ] Dashboard lists all jobs with integer scores in descending order.
- [ ] Candidate applies once; a second apply is rejected (`409`).
- [ ] Employer sees applicants sorted by score; changes status through all four
      values; invalid status is rejected.
- [ ] Employer creates a future 30-minute slot; a 60-minute or past slot is
      rejected.
- [ ] Candidate books an `Interviewing` application; both sides see the booking.
- [ ] Booked slot cannot be deleted; job with applications/slots cannot be
      deleted (`409`).
- [ ] After the demo, run `python -m app.cli seed` again to restore seed state.

## 4. GitHub audit setup (Week 12)

- [ ] `.github/ISSUE_TEMPLATE/audit_bug_report.yml` is present and GitHub shows
      the "Cross-team audit bug report" issue form.
- [ ] All labels from `.github/labels.yml` are imported (`audit:*`, `type:*`,
      `status:*`).
- [ ] The repository stays publicly readable **08:00–20:00, Monday–Friday of
      Week 12** (course timezone). Unavailability costs 0.2 audit points/hour.
- [ ] At least one member monitors new issues during the audit window and
      replies with evidence, without marking their own reports fixed.

## 5. Peer-audit readiness (our team as auditor)

- [ ] Read the target team's `SPEC.md` and `INSTALL.md` before testing.
- [ ] Build from the **latest commit on the target's `main`** using their
      `Dockerfile`; never modify their source to make the build pass.
- [ ] Record the full 40-character commit SHA in every finding.
- [ ] Use the course Issue Form with exact reproduction commands, expected
      behavior with the requirement/spec reference, and actual behavior with
      secrets redacted.
- [ ] File one issue per root cause; search open and closed issues first.
- [ ] Respect the safety boundary: local checkout only, no load/DoS/destructive
      testing, no deployed URLs or third-party accounts.

## 6. Repairs (if our team receives findings)

- [ ] Confirm or reject each report with evidence; do not mark your own report.
- [ ] Add a regression test that fails before and passes after the fix.
- [ ] Fix through the normal review process and link the fix commit/PR in the
      issue.
- [ ] After the repair, rebuild from the fix commit and attach regression
      evidence before the repair deadline.

## 7. Final checks

- [ ] `TEAM.md` has real names and student IDs (or `000000000` for missing
      members).
- [ ] `README.md` mapping table names still match the tests on the graded
      commit.
- [ ] `SPEC.md` matches the graded commit (no aspirational features).
- [ ] Presentation rehearsed with the demo data reset.
- [ ] Course-site submission completed with the commit URL, not a branch URL.
