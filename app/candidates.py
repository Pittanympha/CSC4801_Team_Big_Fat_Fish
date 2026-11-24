"""Candidate dashboard, profile, resume, applications, and booking routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import services
from .constants import ROLE_CANDIDATE
from .errors import AppError, ForbiddenError, ValidationError
from .security import current_user, login_required

bp = Blueprint("candidate", __name__, url_prefix="/candidate")


@bp.get("/")
@login_required(ROLE_CANDIDATE)
def dashboard():
    user = current_user()
    jobs = services.list_recommended_jobs(user["id"])
    profile = services.get_candidate_profile(user["id"])
    return render_template("candidate/dashboard.html", jobs=jobs, profile=profile)


@bp.route("/profile", methods=["GET", "POST"])
@login_required(ROLE_CANDIDATE)
def profile():
    user = current_user()
    if request.method == "POST":
        try:
            services.update_candidate_profile(
                candidate_id=user["id"],
                display_name=request.form.get("display_name", ""),
                skills_raw=request.form.get("skills", ""),
                resume_text=request.form.get("resume_text", ""),
            )
        except AppError as exc:
            profile_data = {
                "id": user["id"],
                "display_name": request.form.get("display_name", ""),
                "skills": [
                    part.strip()
                    for part in request.form.get("skills", "").split(",")
                    if part.strip()
                ],
                "resume_text": request.form.get("resume_text", ""),
                "email": user["email"],
            }
            return (
                render_template(
                    "candidate/profile.html",
                    profile=profile_data,
                    skills_text=request.form.get("skills", ""),
                    error=exc.message,
                ),
                exc.status,
            )
        flash("Profile saved. Matching uses these skills immediately.", "success")
        return redirect(url_for("candidate.profile"))

    profile_data = services.get_candidate_profile(user["id"])
    return render_template(
        "candidate/profile.html",
        profile=profile_data,
        skills_text=", ".join(profile_data["skills"]),
        error=None,
    )


@bp.get("/resume/<int:candidate_id>")
@login_required()
def resume(candidate_id: int):
    """Resumes are private: only the owning candidate may read one."""
    user = current_user()
    if user["role"] != ROLE_CANDIDATE or user["id"] != candidate_id:
        raise ForbiddenError("Resume contents are private to the owning candidate.")
    resume_text = services.get_resume(candidate_id)
    return render_template(
        "candidate/resume.html",
        resume_text=resume_text,
        candidate_name=user["display_name"],
    )


@bp.get("/jobs/<int:job_id>")
@login_required(ROLE_CANDIDATE)
def job_detail(job_id: int):
    user = current_user()
    job = services.get_candidate_job(user["id"], job_id)
    return render_template("candidate/job_detail.html", job=job)


@bp.post("/jobs/<int:job_id>/apply")
@login_required(ROLE_CANDIDATE)
def apply(job_id: int):
    user = current_user()
    services.create_application(user["id"], job_id)
    flash("Application submitted with status Pending.", "success")
    return redirect(url_for("candidate.applications"))


@bp.get("/applications")
@login_required(ROLE_CANDIDATE)
def applications():
    user = current_user()
    applications_list = services.list_candidate_applications(user["id"])
    return render_template(
        "candidate/applications.html", applications=applications_list
    )


@bp.post("/applications/<int:application_id>/book")
@login_required(ROLE_CANDIDATE)
def book(application_id: int):
    user = current_user()
    slot_id = request.form.get("slot_id", type=int)
    if slot_id is None:
        raise ValidationError("Choose an interview slot.")
    services.book_slot(user["id"], application_id, slot_id)
    flash("Interview booked. The employer can see the booking.", "success")
    return redirect(url_for("candidate.applications"))
