from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import re
from datetime import date

from app.audit import execute_audited, log_action
from flask_login import current_user
from app.models.db import execute, fetch_all, fetch_one
from app.security import role_required

patients_bp = Blueprint("patients", __name__, url_prefix="/patients")
PAGE_SIZE = 10


def _patient_form_values():
    values = {
        "full_name": request.form.get("full_name", "").strip()[:160],
        "date_of_birth": request.form.get("date_of_birth") or None,
        "phone": request.form.get("phone", "").strip()[:30] or None,
        "email": request.form.get("email", "").strip().lower()[:254] or None,
        "address": request.form.get("address", "").strip()[:300] or None,
    }
    if values["date_of_birth"]:
        try:
            date.fromisoformat(values["date_of_birth"])
        except ValueError:
            values["date_of_birth"] = "!invalid!"
    if values["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        values["email"] = "!invalid!"
    if values["phone"] and not re.fullmatch(r"[+0-9() .-]{5,30}", values["phone"]):
        values["phone"] = "!invalid!"
    return values


@patients_bp.get("")
@role_required("admin", "medecin", "secretaire")
def list_patients():
    search = request.args.get("q", "").strip()[:100]
    page = max(request.args.get("page", 1, type=int), 1)
    wildcard = f"%{search}%"
    where = "archived = FALSE AND (%s = '' OR full_name ILIKE %s OR phone ILIKE %s)"
    count = fetch_one(f"SELECT COUNT(*) AS count FROM patients WHERE {where}", (search, wildcard, wildcard))["count"]
    rows = fetch_all(
        f"SELECT id, full_name, date_of_birth, phone, email FROM patients WHERE {where} "
        "ORDER BY full_name LIMIT %s OFFSET %s",
        (search, wildcard, wildcard, PAGE_SIZE, (page - 1) * PAGE_SIZE),
    )
    return render_template("patients/list.html", patients=rows, search=search, page=page, pages=max((count + PAGE_SIZE - 1) // PAGE_SIZE, 1))


@patients_bp.route("/new", methods=["GET", "POST"])
@role_required("admin", "medecin", "secretaire")
def create_patient():
    if request.method == "POST":
        values = _patient_form_values()
        if not values["full_name"] or "!invalid!" in values.values():
            flash("Vérifiez le nom, la date de naissance, l'adresse e-mail et le téléphone.", "danger")
        else:
            patient = execute_audited(
                "INSERT INTO patients (full_name, date_of_birth, phone, email, address) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                tuple(values.values()),
                "Création du dossier patient",
                None,
                returning=True,
            )
            flash("Le dossier patient a été créé.", "success")
            return redirect(url_for("patients.patient_detail", patient_id=patient["id"]))
    return render_template("patients/form.html", patient=None, title="Nouveau patient")


@patients_bp.get("/<int:patient_id>")
@role_required("admin", "medecin", "secretaire")
def patient_detail(patient_id: int):
    patient = fetch_one("SELECT * FROM patients WHERE id = %s AND archived = FALSE", (patient_id,))
    if not patient:
        abort(404)
    log_action("Consultation du dossier patient", patient_id)
    is_doctor = current_user.role == "medecin"
    consultations = []
    documents = []
    prescriptions = []
    if is_doctor:
        consultations = fetch_all(
            "SELECT c.id, c.consulted_at, c.note, u.name AS doctor_name FROM consultations c "
            "JOIN users u ON u.id = c.doctor_id WHERE c.patient_id = %s ORDER BY c.consulted_at DESC",
            (patient_id,),
        )
        documents = fetch_all(
            "SELECT id, created_at, label, file_type FROM documents WHERE patient_id = %s ORDER BY created_at DESC",
            (patient_id,),
        )
        prescriptions = fetch_all(
            "SELECT p.id, p.prescribed_at, p.medicines, p.instructions, u.name AS doctor_name "
            "FROM prescriptions p JOIN users u ON u.id = p.doctor_id "
            "WHERE p.patient_id = %s ORDER BY p.prescribed_at DESC",
            (patient_id,),
        )
    return render_template(
        "patients/detail.html",
        patient=patient,
        consultations=consultations,
        documents=documents,
        prescriptions=prescriptions,
        is_doctor=is_doctor,
    )


@patients_bp.route("/<int:patient_id>/edit", methods=["GET", "POST"])
@role_required("admin", "medecin", "secretaire")
def edit_patient(patient_id: int):
    patient = fetch_one("SELECT * FROM patients WHERE id = %s AND archived = FALSE", (patient_id,))
    if not patient:
        abort(404)
    if request.method == "POST":
        values = _patient_form_values()
        if not values["full_name"] or "!invalid!" in values.values():
            flash("Vérifiez le nom, la date de naissance, l'adresse e-mail et le téléphone.", "danger")
        else:
            execute_audited(
                "UPDATE patients SET full_name = %s, date_of_birth = %s, phone = %s, email = %s, "
                "address = %s, updated_at = NOW() WHERE id = %s",
                (*values.values(), patient_id),
                "Modification du dossier patient",
                patient_id,
            )
            flash("Le dossier patient a été mis à jour.", "success")
            return redirect(url_for("patients.patient_detail", patient_id=patient_id))
    return render_template("patients/form.html", patient=patient, title="Modifier le patient")