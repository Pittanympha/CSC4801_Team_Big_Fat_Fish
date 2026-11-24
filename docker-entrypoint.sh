#!/bin/sh
# First container start seeds the deterministic demo data; later starts keep
# the SQLite volume untouched. Run `python -m app.cli seed` explicitly to reset.
set -eu

DB_PATH="${DATABASE_PATH:-/data/app.db}"

if [ ! -f "$DB_PATH" ]; then
    echo "No database at $DB_PATH; creating schema and demo data."
    python -m app.cli seed
else
    echo "Using existing database at $DB_PATH."
    python -m app.cli init-db
fi

exec python run.py
