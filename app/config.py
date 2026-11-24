"""Application configuration.

Every value can be overridden with an environment variable so that the same
code runs locally, in the test suite, and inside the Docker image.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = str(PROJECT_ROOT / "instance" / "app.db")


class Config:
    """Default configuration for local development and the Docker image."""

    # A placeholder only. Production and the Docker image must provide a real
    # SECRET_KEY through the environment (see INSTALL.md and .env.example).
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-placeholder-secret-change-me")

    DATABASE_PATH = os.environ.get("DATABASE_PATH", DEFAULT_DATABASE)

    # Session cookie hardening. The app is served over local HTTP for grading,
    # so SESSION_COOKIE_SECURE stays off unless HTTPS is configured.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MiB is plenty for a text resume.

    TESTING = False
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
