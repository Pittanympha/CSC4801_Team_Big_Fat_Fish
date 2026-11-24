"""Employer company, job posting, applicant, and availability routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import services
from .constants import ROLE_EMPLOYER
from .errors import AppError, ValidationError
from .security import current_user, login_required

bp = Blueprint("employer", __name__, url_prefix="/employer")


@bp.get("/")
@login_required(ROLE_EMPLOYER)
def dashboard():
    user = current_user()
    jobs = services.list_employer_jobs(user["id"])
    company = services.get_company_profile(user["id"])
    totals = {
        "jobs": len(jobs),
        "applications": sum(job["application_count"] for job in jobs),
        "slots": sum(job["slot_count"] for job in jobs),
        "interviewing": sum(
            1
            for job in jobs
            for applicant in services.list_applicants(user["id"], job["id"])
            if applicant["status"] == "Interviewing"
        ),
    }
    return render_template(
        "employer/dashboard.html", jobs=jobs, company=company, totals=totals
    )


@bp.route("/company", methods=["GET", "POST"])
@login_required(ROLE_EMPLOYER)
def company():
    user = current_user()
    if request.method == "POST":
        try:
            services.update_company_profile(
                user["id"],
                request.form.get("company_name", ""),
                request.form.get("description", ""),
            )
        except AppError as exc:
            company_data = {
                "company_name": request.form.get("company_name", ""),
                "description": request.form.get("description", ""),
            }
            return (
                render_template(
                    "employer/company.html", company=company_data, error=exc.message
                ),
                exc.status,
            )
        flash("Company profile saved.", "success")
        return redirect(url_for("employer.company"))
    return render_template(
        "employer/company.html", company=services.get_company_profile(user["id"]), error=None
    )


@bp.route("/jobs/new", methods=["GET", "POST"])
@login_required(ROLE_EMPLOYER)
def job_new():
    user = current_user()
    if request.method == "POST":
        try:
            job_id = services.save_job(
                user["id"],
                None,
                request.form.get("title", ""),
                request.form.get("description", ""),
                request.form.get("skills", ""),
            )
        except AppError as exc:
            job = {
                "title": request.form.get("title", ""),
                "description": request.form.get("description", ""),
            }
            return (
                render_template(
                    "employer/job_form.html",
                    job=job,
                    skills_text=request.form.get("skills", ""),
                    is_new=True,
                    error=exc.message,
                ),
                exc.status,
            )
        flash("Job posted.", "success")
        return redirect(url_for("employer.job_slots", job_id=job_id))
    return render_template(
        "employer/job_form.html", job=None, skills_text="", is_new=True, error=None
    )


@bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required(ROLE_EMPLOYER)
def job_edit(job_id: int):
    user = current_user()
    job = services.get_employer_job(user["id"], job_id)
    if request.method == "POST":
        try:
            services.save_job(
                user["id"],
                job_id,
                request.form.get("title", ""),
                request.form.get("description", ""),
                request.form.get("skills", ""),
            )
        except AppError as exc:
            job_data = {
                "id": job_id,
                "title": request.form.get("title", ""),
                "description": request.form.get("description", ""),
            }
            return (
                render_template(
                    "employer/job_form.html",
                    job=job_data,
                    skills_text=request.form.get("skills", ""),
                    is_new=False,
                    error=exc.message,
                ),
                exc.status,
            )
        flash("Job updated.", "success")
        return redirect(url_for("employer.dashboard"))
    return render_template(
        "employer/job_form.html",
        job=job,
        skills_text=", ".join(job["required_skills"]),
        is_new=False,
        error=None,
    )


@bp.post("/jobs/<int:job_id>/delete")
@login_required(ROLE_EMPLOYER)
def job_delete(job_id: int):
    user = current_user()
    services.delete_job(user["id"], job_id)
    flash("Job deleted.", "success")
    return redirect(url_for("employer.dashboard"))


@bp.get("/jobs/<int:job_id>/applicants")
@login_required(ROLE_EMPLOYER)
def applicants(job_id: int):
    user = current_user()
    job = services.get_employer_job(user["id"], job_id)
    applicants_list = services.list_applicants(user["id"], job_id)
    return render_template(
        "employer/applicants.html", job=job, applicants=applicants_list
    )


@bp.post("/applications/<int:application_id>/status")
@login_required(ROLE_EMPLOYER)
def application_status(application_id: int):
    user = current_user()
    new_status = request.form.get("status", "")
    if not new_status:
        raise ValidationError("Choose a status.")
    job_id = services.update_application_status(user["id"], application_id, new_status)
    flash(f"Application status set to {new_status}.", "success")
    return redirect(url_for("employer.applicants", job_id=job_id))


@bp.route("/jobs/<int:job_id>/slots", methods=["GET", "POST"])
@login_required(ROLE_EMPLOYER)
def job_slots(job_id: int):
    user = current_user()
    job = services.get_employer_job(user["id"], job_id)
    if request.method == "POST":
        try:
            services.create_slot(
                user["id"],
                job_id,
                request.form.get("start_at", ""),
                request.form.get("end_at", ""),
            )
        except AppError as exc:
            return (
                render_template(
                    "employer/slots.html",
                    job=job,
                    slots=services.list_slots(user["id"], job_id),
                    error=exc.message,
                ),
                exc.status,
            )
        flash("Availability created.", "success")
        return redirect(url_for("employer.job_slots", job_id=job_id))
    return render_template(
        "employer/slots.html",
        job=job,
        slots=services.list_slots(user["id"], job_id),
        error=None,
    )


@bp.post("/slots/<int:slot_id>/delete")
@login_required(ROLE_EMPLOYER)
def slot_delete(slot_id: int):
    user = current_user()
    job_id = services.delete_slot(user["id"], slot_id)
    flash("Availability deleted.", "success")
    return redirect(url_for("employer.job_slots", job_id=job_id))
