"""UTC time helpers.

The whole application stores and compares timestamps as ISO-8601 UTC strings
ending in ``Z``. The UI labels every time as UTC, which is the documented,
unambiguous timezone required by FP-SCHED-1.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    """Parse an ISO string from a form or database into an aware UTC datetime.

    Naive values (including HTML ``datetime-local`` input) are interpreted as
    UTC, matching the label shown in the UI.
    """
    text = (value or "").strip()
    if not text:
        raise ValueError("missing datetime")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_utc(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parse_utc(value).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def local_input_value(value: str | None) -> str:
    """Render a stored UTC timestamp for an HTML ``datetime-local`` input."""
    if not value:
        return ""
    try:
        return parse_utc(value).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return ""
