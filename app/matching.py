"""Deterministic skill-overlap matching (FP-MATCH-1).

This module is the single matching implementation used by both the candidate
dashboard and the employer applicant list. It has no database or Flask
dependency, which keeps the contract easy to unit-test.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def normalize_skills(values: Iterable[str] | str | None) -> set[str]:
    """Normalize skill input to a set.

    Trims surrounding whitespace, lower-cases, drops empty values, and removes
    duplicates. A comma-separated string is accepted for form handling; any
    other iterable of strings (or ``None``) is also supported.
    """
    if values is None:
        return set()
    if isinstance(values, str):
        parts: Iterable[str] = values.split(",")
    else:
        parts = values

    normalized: set[str] = set()
    for raw in parts:
        if raw is None:
            continue
        for piece in str(raw).split(","):
            skill = piece.strip().lower()
            if skill:
                normalized.add(skill)
    return normalized


def calculate_match_score(
    candidate_skills: Iterable[str] | str | None,
    required_skills: Iterable[str] | str | None,
) -> int:
    """Return the required integer score from 0 to 100.

    ``score = 100`` when the required-skill set is empty, otherwise
    ``floor(100 * |C intersect R| / |R|)``. Resume text is never an input.
    """
    candidate = normalize_skills(candidate_skills)
    required = normalize_skills(required_skills)
    if not required:
        return 100
    return math.floor(100 * len(candidate & required) / len(required))


def job_sort_key(job: dict) -> tuple:
    """Candidate dashboard order: score desc, title asc, stable job id asc."""
    return (-job["score"], job["title"].casefold(), job["id"])


def applicant_sort_key(applicant: dict) -> tuple:
    """Employer applicant order: score desc, name asc, stable candidate id asc."""
    return (-applicant["score"], applicant["display_name"].casefold(), applicant["candidate_id"])
