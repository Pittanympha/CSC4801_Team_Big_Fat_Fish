# INSTALL — run TalentBridge from a clean checkout

This is the exact procedure for the graded commit. The local Python flow was
executed on Windows 11 with Python 3.13.7; the Docker flow requires a running
Docker daemon and network access to install Flask during the build. The same
commands work on Windows, macOS, and Linux unless noted.

## 1. Prerequisites

| Tool | Version used and tested | Minimum |
|---|---|---|
| Python | 3.13.7 | 3.13 |
| pip | bundled with Python (`python -m pip`) | any recent |
| Flask | 3.1.3 (installed from `requirements.txt`) | pinned |
| Docker | 29.4.3 (optional for local runs, required for the grading image) | 24+ |
| Git | any recent | any |

No Node.js, database server, external API key, or paid credential is required.
The application and the automated tests run without network access after the
Python packages are installed.

> Windows note: if `python` opens the Microsoft Store, use the `py` launcher
> (`py -3.13`) instead of `python` in the commands below.

## 2. Local installation (about two minutes)

From the repository root:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate

# 2. Install the single direct dependency (Flask and its dependencies)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 3. Create the SQLite schema (idempotent migration 001)
python -m app.cli init-db

# 4. Reset and load the deterministic demo data
python -m app.cli seed

# 5. Start the local server
python -m app.cli run
```

Open <http://127.0.0.1:8000>. The first page is the landing page; use
`hr@acme.test` or `alice@demo.test` with the demo password documented in
[`README.md`](README.md).

Stop the server with `Ctrl+C`.

### Run without activating the virtual environment

Every command works with the interpreter path directly:

```bash
# Windows
.venv\Scripts\python.exe -m app.cli run

# macOS / Linux
.venv/bin/python -m app.cli run
```

## 3. Environment variables

The application reads configuration from the process environment. It does not
auto-load `.env` files (no extra dependency); export the variables in your shell
or pass them to `docker run`.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-only-placeholder-secret-change-me` | Signs session cookies. **Replace it** anywhere beyond a local demo. |
| `DATABASE_PATH` | `instance/app.db` | SQLite file. Parent directory is created automatically. |
| `HOST` | `127.0.0.1` for `app.cli run`, `0.0.0.0` for `run.py` | Bind address. |
| `PORT` | `8000` | HTTP port. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` only behind HTTPS. |
| `FLASK_DEBUG` | `0` | Set to `1` for the Flask debugger; keep `0` when grading. |

`.env.example` contains placeholders only. Copy it to `.env` and fill in your own
values if you use a process manager that loads `.env`; never commit `.env`.

### PowerShell example

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-value"
$env:DATABASE_PATH = "instance/app.db"
$env:PORT = "8000"
python -m app.cli run
```

## 4. Database setup, migrations, and reset

- `app/schema.sql` is migration **001**. `python -m app.cli init-db` applies it
  with `CREATE TABLE IF NOT EXISTS`, so it is safe to run on every start and on
  an existing database.
- The schema version is recorded in SQLite `PRAGMA user_version = 1`.
- The seed command (`python -m app.cli seed`) calls `init-db` first, then deletes
  all rows and re-inserts the deterministic data. It is the documented reset
  command for local demos and for graders.
- To fully recreate the database file:

  ```bash
  # macOS / Linux
  rm -f instance/app.db instance/app.db-wal instance/app.db-shm
  python -m app.cli init-db
  python -m app.cli seed

  # Windows PowerShell
  Remove-Item -Force -ErrorAction SilentlyContinue instance\app.db*
  python -m app.cli init-db
  python -m app.cli seed
  ```

No migration framework is needed or used: this project has one initial schema
and no destructive upgrade path.

## 5. Seed data and demo accounts

```bash
python -m app.cli seed
```

This creates seven local-only accounts (all with password `DemoPass123!`):

| Email | Role | Seeded state |
|---|---|---|
| `alice@demo.test` | Candidate | Python + SQL; Backend application `Interviewing`, one booked interview |
| `bob@demo.test` | Candidate | Python; Backend application `Pending` |
| `carol@demo.test` | Candidate | Rust; Rust job application `Accepted` |
| `dave@demo.test` | Candidate | Python + SQL; Backend application `Interviewing`, no booking (race candidate) |
| `erin@demo.test` | Candidate | Python + SQL; Backend application `Interviewing`, no booking (race candidate) |
| `hr@acme.test` | Employer | Acme Robotics; 3 jobs, applicants, 2 slots (one booked) |
| `hr@globex.test` | Employer | Globex Analytics; 1 job, 1 slot |

The data covers all four application statuses, the four required matching
examples, and two `Interviewing` candidates eligible to race for the same
available slot. Emails use the reserved `.test` domain; the password is clearly
a demo credential and must never be reused.

## 6. Run the unit tests

```bash
python -m unittest discover -s tests -v
```

- Runs non-interactively, uses the standard library only, and exits non-zero on
  failure (verified locally with Python 3.13.7).
- Each test receives a unique temporary SQLite database under
  `instance/test-tmp/`; the developer database is never touched.
- The suite includes the concurrent booking test, the four matching examples,
  authorization boundaries, SQL-injection and XSS cases, seed checks, and the
  requirement-mapping/documentation checks.

A single test module can be run with, for example:

```bash
python -m unittest tests.test_scheduling -v
```

## 7. Docker (build the complete environment)

The repository root contains the `Dockerfile`. It installs Flask from
`requirements.txt`, copies the application, migrations, seed script, and tests,
creates a non-root user, and starts the server through
`docker-entrypoint.sh`.

```bash
# 1. Build (from a clean checkout of the graded commit)
docker build -t talentbridge .

# 2. Start, with a named volume so the database survives restarts
docker run -d --name talentbridge \
  -p 127.0.0.1:8000:8000 \
  -v talentbridge_data:/data \
  talentbridge

# 3. Confirm it is healthy
docker ps
curl http://127.0.0.1:8000/healthz
```

The first start creates `/data/app.db` and loads the demo seed automatically.
Later starts reuse the volume. If you want a clean reset at any time:

```bash
docker exec talentbridge python -m app.cli seed
```

Run the required test suite inside the built environment:

```bash
docker exec talentbridge python -m unittest discover -s tests -v
```

Inspect startup logs:

```bash
docker logs talentbridge
```

Stop and remove the container (the named volume keeps the data):

```bash
docker stop talentbridge
docker rm talentbridge
```

Remove the volume too for a completely clean run:

```bash
docker volume rm talentbridge_data
```

### What the Dockerfile does not need

- No image tar is uploaded or required.
- No private registry, cloud account, or external database image.
- No secret at build time. `SECRET_KEY` has a clearly marked local-docker
  placeholder and can be overridden with `-e SECRET_KEY=...`.
- No undocumented command: build, run, seed, and test are all listed above.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | The virtual environment is not active or dependencies were not installed. Run `python -m pip install -r requirements.txt`. |
| `ModuleNotFoundError: No module named 'app'` | You are not in the repository root. `cd` to the directory containing `run.py` and `app/`. |
| `sqlite3.OperationalError: unable to open database file` | The database parent directory is not writable, or `DATABASE_PATH` points to a non-existent drive. Use the default `instance/app.db` or create the directory. |
| `sqlite3.OperationalError: database is locked` | Another server/test process is writing the same database file. Stop it, or give each process its own `DATABASE_PATH`. The app sets a 10-second busy timeout. |
| Port 8000 already in use | `python -m app.cli run --port 8001`, or `PORT=8001`. |
| Login always fails after seeding | The seed resets passwords; use the demo password from README. A stale browser cookie can also be cleared by logging out. |
| Docker: `Cannot connect to the Docker daemon` | Start Docker Desktop/daemon first. |
| Docker build cannot reach PyPI | The build needs network access to install Flask. Configure your proxy or pre-pull `python:3.13-slim`; no application code downloads anything at run time. |
| Docker container exits immediately | Check `docker logs talentbridge`. A common cause is a `/data` volume owned by another user; remove the volume and recreate it. |
| Windows: `python` opens the Microsoft Store | Use `py -3.13` (or the full interpreter path) in every command. |
| Tests leave files in `instance/test-tmp` | A crashed test can leave a temporary directory. It is ignored by Git and safe to delete. |

## 9. Clean-checkout verification checklist

Run these in order on a fresh clone of the graded commit:

1. `python -m venv .venv` and activate it.
2. `python -m pip install -r requirements.txt`.
3. `python -m app.cli init-db`.
4. `python -m app.cli seed`.
5. `python -m unittest discover -s tests -v` → ends with `OK` and exit code 0.
6. `python -m app.cli run` → landing page loads at `http://127.0.0.1:8000`.
7. Log in as `alice@demo.test`, open **My applications**, and confirm the booked
   interview is visible.
8. Log in as `hr@acme.test`, open **Applicants** for Backend Engineer, and
   confirm applicants are ordered Alice (100), Dave (100), Erin (100), Bob (50).
9. `docker build -t talentbridge .` and `docker run` as in Section 7.
10. `docker exec talentbridge python -m unittest discover -s tests -v`.
