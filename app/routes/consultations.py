from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import execute_audited, log_action
from app.models.db import fetch_all, fetch_one
from app.security import role_required

consultations_bp = Blueprint("consultations", __name__, url_prefix="/patients/<int:patient_id>/consultations")


@consultations_bp.get("")
@role_required("medecin")
def list_consultations(patient_id: int):
    patient = fetch_one("SELECT id, full_name FROM patients WHERE id = %s AND archived = FALSE", (patient_id,))
    if not patient:
        abort(404)
    log_action("Consultation de l'historique médical", patient_id)
    consultations = fetch_all(
        "SELECT id, consulted_at, note FROM consultations WHERE patient_id = %s ORDER BY consulted_at DESC",
        (patient_id,),
    )
    return render_template("consultations/list.html", patient=patient, consultations=consultations)


@consultations_bp.route("/new", methods=["GET", "POST"])
@role_required("medecin")
def create_consultation(patient_id: int):
    patient = fetch_one("SELECT id, full_name FROM patients WHERE id = %s AND archived = FALSE", (patient_id,))
    if not patient:
        abort(404)
    if request.method == "POST":
        note = request.form.get("note", "").strip()
        if not note or len(note) > 10000:
            flash("La note est obligatoire et ne peut dépasser 10 000 caractères.", "danger")
        else:
            execute_audited(
                "INSERT INTO consultations (patient_id, doctor_id, note) VALUES (%s, %s, %s)",
                (patient_id, int(current_user.id), note),
                "Ajout d'une note de consultation",
                patient_id,
            )
            flash("La note de consultation a été enregistrée.", "success")
            return redirect(url_for("patients.patient_detail", patient_id=patient_id))
    return render_template("consultations/form.html", patient=patient)