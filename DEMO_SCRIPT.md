# Demo script (10-minute presentation)

Reset to the deterministic seed before every rehearsal and before presenting:

```bash
python -m app.cli seed
python -m app.cli run
```

All accounts use password `DemoPass123!`. Use two browser profiles or one normal
window and one private window so candidate and employer sessions do not clash.

## 1. Candidate value (2 minutes)

1. Log in as `alice@demo.test`.
2. Show the dashboard: every role is listed, each card shows the integer match
   score, company, required-skill chips, and a description link. The list is
   sorted highest score first.
3. Open **Backend Engineer**: 100% because Python and SQL are both required.
4. Open **My applications**: status `Interviewing` and the booked 30-minute
   interview are visible; the booking is the one seeded for Alice.
5. Open **Profile**: skills and private resume. Point out that resume text is not
   used in scoring.

## 2. Apply and duplicate protection (1 minute)

1. Still as Alice, open a role she has not applied to (for example **Data
   Analyst** at Globex) and click **Apply now**.
2. Show `Pending` on **My applications**.
3. Submit the same application again (browser Back, then Apply). Show the
   `409 Conflict` page: "You have already applied to this job."

## 3. Employer value (2 minutes)

1. Log in as `hr@acme.test` in the second window.
2. Dashboard shows 3 jobs, applicant/slot counts.
3. Open **Applicants** for Backend Engineer: order is Alice (100), Dave (100),
   Erin (100), Bob (50); every row shows skills, match, status, booking.
4. Change Bob from `Pending` to `Interviewing` and show the success flash.

## 4. Availability and booking (2 minutes)

1. As Acme, open **Availability** for Backend Engineer.
2. Create a slot: enter a start exactly 30 minutes before the end, both in UTC,
   tomorrow or later. Show the new Available row.
3. Try a 60-minute slot: show the `400` rejection message.
4. As Dave (`dave@demo.test`), open **My applications**; the seeded race slot and
   the new slot are selectable. Book one; show the confirmation.
5. Back as Acme, the slot is now **Booked** and its Delete button is gone. Try to
   delete it by URL/POST if you want to show the `409` contract.

## 5. Concurrency story (1 minute, no live race required)

Explain `SPEC.md` §8: `BEGIN IMMEDIATE` serializes writers, and
`UNIQUE(bookings.slot_id)` lets exactly one insert win. The test
`test_fp_sched_3_concurrent_booking_exactly_one_wins` starts two threads on a
barrier and asserts one success, one `409 Slot already booked`, and one row.

Optionally run:

```bash
python -m unittest tests.test_scheduling.ConcurrentBookingTests -v
```

## 6. Security spot checks (1 minute)

1. As Alice, copy the resume URL and open it in the employer window: `403`.
2. Log out and try the login email `' OR '1'='1' --` with any password: `401`,
   no bypass.
3. Save a display name containing `<script>alert(1)</script>`; show that the
   page renders the text instead of executing a script.
4. Point to the four statuses and explain that only the owning employer's route
   can change them.

## 7. Test evidence and close (1 minute)

```bash
python -m unittest discover -s tests -v
```

Ends with `OK` (100 tests). Show `README.md` requirement–test mapping table and
`SPEC.md` booking transaction section. Close with known limitations: no CSRF
tokens (SameSite=Lax), development server, SQLite single writer, no LLM feature.

## Reset after the demo

```bash
python -m app.cli seed
```
