"""SQLite access layer.

All SQL in the application is executed with ``?`` placeholders and bound
parameters.  The connection runs in autocommit mode; multi-statement business
operations opt into an explicit ``BEGIN IMMEDIATE`` transaction through
:func:`transaction`, which is what makes interview booking atomic.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite connection, creating it on first use."""
    if "db" not in g:
        path = current_app.config["DATABASE_PATH"]
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            path,
            timeout=10.0,
            isolation_level=None,  # autocommit; transactions are explicit
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        if path != ":memory:":
            connection.execute("PRAGMA synchronous = NORMAL")
        g.db = connection
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def transaction():
    """Run a block inside ``BEGIN IMMEDIATE`` and commit or roll back.

    ``BEGIN IMMEDIATE`` acquires SQLite's write lock before the first read, so
    concurrent booking attempts are serialized by the database itself; combined
    with the UNIQUE constraint on ``bookings.slot_id`` this guarantees that at
    most one booking can ever win a race for a slot.
    """
    connection = get_db()
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:  # pragma: no cover - defensive
            pass
        raise
    else:
        connection.execute("COMMIT")


def init_db() -> None:
    """Apply the idempotent schema. Safe to run on every container start."""
    connection = get_db()
    if connection.execute("PRAGMA database_list").fetchone()["file"]:
        # WAL is persistent once enabled; doing it here avoids changing the
        # journal mode from concurrently opening request connections.
        connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    connection.execute("PRAGMA user_version = 1")
