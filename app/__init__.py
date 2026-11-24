"""TalentBridge application factory."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, url_for
from werkzeug.exceptions import HTTPException

from .config import Config
from .constants import APPLICATION_STATUSES, ROLE_CANDIDATE, ROLE_EMPLOYER
from .db import close_db
from .errors import AppError
from .security import current_user
from .timeutil import format_utc, iso_z, local_input_value, utc_now


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    database_path = app.config["DATABASE_PATH"]
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)

    from .auth import bp as auth_bp
    from .candidates import bp as candidate_bp
    from .employers import bp as employer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(employer_bp)

    @app.get("/")
    def home():
        user = current_user()
        if user is None:
            return render_template("index.html")
        if user["role"] == ROLE_CANDIDATE:
            return redirect(url_for("candidate.dashboard"))
        if user["role"] == ROLE_EMPLOYER:
            return redirect(url_for("employer.dashboard"))
        return render_template("index.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.context_processor
    def inject_globals():
        return {
            "user": current_user(),
            "application_statuses": APPLICATION_STATUSES,
            "now_iso": iso_z(utc_now()),
        }

    app.jinja_env.filters["utc"] = format_utc
    app.jinja_env.filters["utc_input"] = local_input_value

    @app.template_filter("status_class")
    def status_class(status: str) -> str:
        return {
            "Pending": "badge badge-pending",
            "Interviewing": "badge badge-interviewing",
            "Rejected": "badge badge-rejected",
            "Accepted": "badge badge-accepted",
        }.get(status, "badge")

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return (
            render_template(
                "errors/error.html",
                status_code=error.status,
                message=error.message,
            ),
            error.status,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return (
            render_template(
                "errors/error.html",
                status_code=error.code or 500,
                message=error.description or "Unexpected error.",
            ),
            error.code or 500,
        )

    return app
