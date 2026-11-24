# Peer-review playbook

A one-page operational summary of the course `PEER_REVIEW.md`. The course
document is normative; this file only helps the team execute it consistently.

## Safety boundary

**Allowed:** read source and docs; build the target's `Dockerfile`; run its
documented tests and local server; write a minimal regression test against the
local checkout; run static/secret/dependency scanners on that checkout.

**Forbidden:** testing deployed URLs, shared staging, real third-party accounts,
or data the target did not provide; load/DoS/resource-exhaustion/destructive
testing; social engineering; secret exfiltration; modifying the target's
branches, PRs, CI, settings, or issues other than your own finding; publishing a
secret or personal data.

Violating the boundary is an academic-integrity issue, not just an invalid report.

## Procedure

1. Clone the target repository and check out the latest commit on `main`.
2. `docker build -t audit-target .` without modifying the source.
3. Follow their `INSTALL.md` to start, migrate, seed, test, and smoke-test.
4. Inspect source for requirements in `REQUIREMENTS.md` and the target's
   `SPEC.md`; reproduce runtime issues in the local environment.
5. Before filing, search open and closed issues for the same root cause.
6. File one issue per root cause with:
   - reporting team, exact 40-character commit SHA;
   - OS/Docker versions and any deviation from `INSTALL.md`;
   - exact reset/seed commands and the smallest request, UI sequence, or test;
   - expected behavior with the requirement ID or spec section;
   - actual behavior (response, exception, assertion, row count), secrets and
     personal data redacted;
   - exactly one `type:*` label plus `audit:report` and `status:needs-triage`.

Screenshots may supplement commands but never replace them. For concurrency
findings, use a synchronization barrier; sequential requests do not prove a
race. For scanner findings, trace to a reachable path and give a harmless local
proof.

## Triage language

- `status:confirmed` — reproducible, in scope, safe, not a duplicate.
- `status:rejected` — fails a valid-finding condition.
- `status:duplicate` — same root cause; link the earlier issue.
- `status:fixed` — fix and regression evidence pass at the linked fix commit.

Reporters must not mark their own report confirmed or fixed. The target team
adds a regression test, fixes the root cause, and links the PR/commit back to the
issue.

## Scoring reminders

- Security finding +2; functional/performance +1; environmental issue +0.5;
  invalid report −0.5; duplicate 0.
- One root cause is one finding even with several symptoms; do not split.
- Repair with a valid record, permanent fix commit, and regression evidence +2;
  incorrect fix/regression claim −0.5.
- Do not fabricate evidence, coordinate duplicates, backdate commits, or hide
  reproduction details.
