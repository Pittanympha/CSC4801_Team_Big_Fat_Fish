"""Command-line entry points.

Usage:
    python -m app.cli init-db
    python -m app.cli seed
    python -m app.cli run [--host 127.0.0.1] [--port 8000]
"""

from __future__ import annotations

import click
from flask import Flask

from . import create_app
from .db import init_db
from .seed import seed_database


def _app() -> Flask:
    return create_app()


@click.group()
def cli() -> None:
    """TalentBridge maintenance commands."""


@cli.command("init-db")
def init_db_command() -> None:
    """Create or upgrade the SQLite schema (idempotent)."""
    app = _app()
    with app.app_context():
        init_db()
    click.echo(f"Database schema ready at {app.config['DATABASE_PATH']}")


@cli.command("seed")
def seed_command() -> None:
    """Reset and load the deterministic demo data (local only)."""
    app = _app()
    with app.app_context():
        init_db()
        summary = seed_database(reset=True)
    click.echo("Seeded demo data:")
    for key in ("users", "jobs", "applications", "slots", "bookings"):
        click.echo(f"  {key}: {summary[key]}")
    click.echo("Demo accounts all use password: DemoPass123!")


@cli.command("run")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, type=int, show_default=True)
def run_command(host: str, port: int) -> None:
    """Start the development HTTP server (threaded)."""
    app = _app()
    app.run(host=host, port=port, threaded=True, debug=app.config["DEBUG"])


if __name__ == "__main__":
    cli()
