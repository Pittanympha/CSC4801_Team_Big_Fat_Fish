"""Authentication, password storage, and server-side authorization helpers."""

from __future__ import annotations

from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


def hash_password(password: str) -> str:
    """Hash a password with scrypt (memory-hard, salted, per-password)."""
    return generate_password_hash(password, method="scrypt")


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def current_user() -> dict | None:
    """Return the signed-in user as a plain dict, or ``None``.

    The role is always re-read from the database; the session only stores the
    user id, so a stale or forged role can never grant access.
    """
    if "current_user" not in g:
        user_id = session.get("user_id")
        g.current_user = None
        if user_id is not None:
            row = get_db().execute(
                "SELECT id, email, role, display_name FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is not None:
                g.current_user = dict(row)
            else:  # account deleted while a session was still valid
                session.clear()
    return g.current_user


def login_user(user_id: int) -> None:
    session.clear()
    session["user_id"] = int(user_id)
    session.permanent = True


def logout_user() -> None:
    session.clear()


def safe_next_url(target: str | None) -> str | None:
    """Only allow same-site relative redirects (prevents open redirects)."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def login_required(role: str | None = None):
    """Enforce authentication and, optionally, one application role.

    Unauthenticated browser navigations are redirected to the login page
    (allowed by FP-AUTH-3); every other unauthenticated request receives 401.
    A signed-in user with the wrong role receives 403.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                if request.method == "GET":
                    return redirect(url_for("auth.login", next=request.path))
                abort(401)
            if role is not None and user["role"] != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
