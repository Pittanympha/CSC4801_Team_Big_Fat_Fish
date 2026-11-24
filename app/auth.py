"""Registration, login, and logout routes (FP-AUTH-1)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import services
from .constants import ROLE_CANDIDATE
from .errors import AppError
from .security import (
    current_user,
    login_required,
    login_user,
    logout_user,
    safe_next_url,
)

bp = Blueprint("auth", __name__)


def _dashboard_url(role: str) -> str:
    if role == ROLE_CANDIDATE:
        return url_for("candidate.dashboard")
    return url_for("employer.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user() is not None:
        return redirect(url_for("home"))

    form = {"email": "", "display_name": "", "role": ROLE_CANDIDATE}
    error = None

    if request.method == "POST":
        form = {
            "email": request.form.get("email", ""),
            "display_name": request.form.get("display_name", ""),
            "role": request.form.get("role", ROLE_CANDIDATE),
        }
        role = form["role"]
        try:
            user_id = services.create_user(
                email=form["email"],
                password=request.form.get("password", ""),
                display_name=form["display_name"],
                role=role,
            )
        except AppError as exc:
            error = exc.message
            return render_template("auth/register.html", form=form, error=error), exc.status

        login_user(user_id)
        flash("Account created. Welcome to TalentBridge!", "success")
        return redirect(_dashboard_url(role))

    return render_template("auth/register.html", form=form, error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("home"))

    next_url = safe_next_url(request.values.get("next"))
    form = {"email": ""}
    error = None

    if request.method == "POST":
        form = {"email": request.form.get("email", "")}
        user = services.authenticate(form["email"], request.form.get("password", ""))
        if user is None:
            error = "Email or password is incorrect."
            return render_template(
                "auth/login.html", form=form, error=error, next_url=next_url
            ), 401
        login_user(user["id"])
        flash(f"Signed in as {user['display_name']}.", "success")
        return redirect(next_url or _dashboard_url(user["role"]))

    return render_template("auth/login.html", form=form, error=error, next_url=next_url)


@bp.post("/logout")
@login_required()
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
