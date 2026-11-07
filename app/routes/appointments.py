from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_action
from app.models.db import execute, fetch_all, fetch_one
from app.security import role_required

appointments_bp = Blueprint("appointments", __name__, url_prefix="/appointments")


@appointments_bp.get("")
@role_required("admin", "medecin", "secretaire")
def list_appointments():
    appointments = fetch_all(
        "SELECT a.id, a.patient_id, a.starts_at, a.reason, a.status, p.full_name, u.name AS doctor_name "
        "FROM appointments a JOIN patients p ON p.id = a.patient_id LEFT JOIN users u ON u.id = a.doctor_id "
        "WHERE a.starts_at >= CURRENT_DATE - INTERVAL '1 day' ORDER BY a.starts_at LIMIT 200"
    )
    doctors = fetch_all("SELECT id, name FROM users WHERE role = 'medecin' AND is_active = TRUE ORDER BY name")
    return render_template("appointments/list.html", appointments=appointments, doctors=doctors)


@appointments_bp.route("/new", methods=["GET", "POST"])
@role_required("admin", "secretaire")
def create_appointment():
    patients = fetch_all("SELECT id, full_name FROM patients WHERE archived = FALSE ORDER BY full_name")
    doctors = fetch_all("SELECT id, name FROM users WHERE role = 'medecin' AND is_active = TRUE ORDER BY name")
    if request.method == "POST":
        try:
            patient_id = int(request.form.get("patient_id", ""))
            doctor_id = int(request.form.get("doctor_id", ""))
            starts_at = datetime.fromisoformat(request.form.get("starts_at", ""))
        except (ValueError, TypeError):
            flash("Veuillez vérifier les informations du rendez-vous.", "danger")
        else:
            if not fetch_one("SELECT id FROM patients WHERE id = %s AND archived = FALSE", (patient_id,)) or not fetch_one(
                "SELECT id FROM users WHERE id = %s AND role = 'medecin' AND is_active = TRUE", (doctor_id,)
            ):
                abort(400)
            reason = request.form.get("reason", "").strip()[:200] or None
            appointment = fetch_one(
                "INSERT INTO appointments (patient_id, doctor_id, starts_at, reason, created_by) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (patient_id, doctor_id, starts_at, reason, int(current_user.id)),
            )
            log_action("Création d'un rendez-vous", patient_id)
            flash("Le rendez-vous a été créé.", "success")
            return redirect(url_for("appointments.list_appointments"))
    return render_template("appointments/form.html", patients=patients, doctors=doctors, appointment=None)


@appointments_bp.route("/<int:appointment_id>/edit", methods=["GET", "POST"])
@role_required("admin", "secretaire")
def edit_appointment(appointment_id: int):
    appointment = fetch_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appointment:
        abort(404)
    patients = fetch_all("SELECT id, full_name FROM patients WHERE archived = FALSE ORDER BY full_name")
    doctors = fetch_all("SELECT id, name FROM users WHERE role = 'medecin' AND is_active = TRUE ORDER BY name")
    if request.method == "POST":
        try:
            patient_id = int(request.form.get("patient_id", ""))
            doctor_id = int(request.form.get("doctor_id", ""))
            starts_at = datetime.fromisoformat(request.form.get("starts_at", ""))
        except (ValueError, TypeError):
            flash("Veuillez vérifier les informations du rendez-vous.", "danger")
        else:
            status = request.form.get("status", "planifie")
            if status not in {"planifie", "annule", "termine"}:
                abort(400)
            if not fetch_one("SELECT id FROM patients WHERE id = %s AND archived = FALSE", (patient_id,)) or not fetch_one(
                "SELECT id FROM users WHERE id = %s AND role = 'medecin' AND is_active = TRUE", (doctor_id,)
            ):
                abort(400)
            execute(
                "UPDATE appointments SET patient_id = %s, doctor_id = %s, starts_at = %s, reason = %s, status = %s "
                "WHERE id = %s",
                (patient_id, doctor_id, starts_at, request.form.get("reason", "").strip()[:200] or None, status, appointment_id),
            )
            log_action("Modification d'un rendez-vous", patient_id)
            flash("Le rendez-vous a été mis à jour.", "success")
            return redirect(url_for("appointments.list_appointments"))
    return render_template("appointments/form.html", patients=patients, doctors=doctors, appointment=appointment)


@appointments_bp.post("/<int:appointment_id>/cancel")
@role_required("admin", "secretaire")
def cancel_appointment(appointment_id: int):
    appointment = fetch_one("SELECT patient_id FROM appointments WHERE id = %s", (appointment_id,))
    if not appointment:
        abort(404)
    execute("UPDATE appointments SET status = 'annule' WHERE id = %s", (appointment_id,))
    log_action("Annulation d'un rendez-vous", appointment["patient_id"])
    flash("Le rendez-vous a été annulé.", "info")
    return redirect(url_for("appointments.list_appointments"))