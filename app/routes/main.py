from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models.db import fetch_all, fetch_one

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
@login_required
def dashboard():
    if current_user.role == "patient":
        return redirect(url_for("portal.patient_home"))
    patients = fetch_one("SELECT COUNT(*) AS count FROM patients WHERE archived = FALSE")
    today = fetch_one(
        "SELECT COUNT(*) AS count FROM appointments WHERE starts_at::date = CURRENT_DATE "
        "AND status = 'planifie'"
    )
    upcoming = fetch_all(
        "SELECT a.id, a.starts_at, a.status, p.id AS patient_id, p.full_name, u.name AS doctor_name "
        "FROM appointments a JOIN patients p ON p.id = a.patient_id "
        "LEFT JOIN users u ON u.id = a.doctor_id "
        "WHERE a.starts_at >= CURRENT_DATE AND a.status = 'planifie' "
        "ORDER BY a.starts_at LIMIT 8"
    )
    return render_template(
        "dashboard.html",
        patient_count=patients["count"],
        appointment_count=today["count"],
        upcoming=upcoming,
    )