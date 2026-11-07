from flask import Blueprint, abort, current_app, redirect, render_template
from flask_login import current_user

from app.audit import log_action
from app.models.db import fetch_all, fetch_one
from app.routes.documents import s3_client
from app.security import role_required

portal_bp = Blueprint("portal", __name__, url_prefix="/espace-patient")


@portal_bp.get("")
@role_required("patient")
def patient_home():
    patient = fetch_one(
        "SELECT id, full_name, date_of_birth, phone, email FROM patients "
        "WHERE user_id = %s AND archived = FALSE",
        (int(current_user.id),),
    )
    if not patient:
        abort(404)
    log_action("Consultation de l'espace patient", patient["id"])
    appointments = fetch_all(
        "SELECT a.starts_at, a.status, u.name AS doctor_name FROM appointments a "
        "JOIN users u ON u.id = a.doctor_id "
        "WHERE a.patient_id = %s AND a.starts_at >= CURRENT_DATE "
        "AND a.status = 'planifie' ORDER BY a.starts_at LIMIT 50",
        (patient["id"],),
    )
    consultations = fetch_all(
        "SELECT c.consulted_at, c.note, u.name AS doctor_name FROM consultations c "
        "JOIN users u ON u.id = c.doctor_id WHERE c.patient_id = %s "
        "ORDER BY c.consulted_at DESC LIMIT 50",
        (patient["id"],),
    )
    documents = fetch_all(
        "SELECT id, created_at, label, file_type FROM documents "
        "WHERE patient_id = %s ORDER BY created_at DESC LIMIT 50",
        (patient["id"],),
    )
    prescriptions = fetch_all(
        "SELECT prescribed_at, medicines, instructions, u.name AS doctor_name "
        "FROM prescriptions p JOIN users u ON u.id = p.doctor_id "
        "WHERE p.patient_id = %s ORDER BY p.prescribed_at DESC LIMIT 50",
        (patient["id"],),
    )
    return render_template(
        "portal/patient_home.html",
        patient=patient,
        appointments=appointments,
        consultations=consultations,
        documents=documents,
        prescriptions=prescriptions,
    )


@portal_bp.get("/documents/<int:document_id>/download")
@role_required("patient")
def download_own_document(document_id: int):
    document = fetch_one(
        "SELECT d.object_key, p.id AS patient_id FROM documents d "
        "JOIN patients p ON p.id = d.patient_id "
        "WHERE d.id = %s AND p.user_id = %s AND p.archived = FALSE",
        (document_id, int(current_user.id)),
    )
    if not document:
        abort(404)
    log_action("Téléchargement de son document médical", document["patient_id"])
    url = s3_client(presigned=True).generate_presigned_url(
        "get_object",
        Params={"Bucket": current_app.config["S3_BUCKET"], "Key": document["object_key"]},
        ExpiresIn=60,
    )
    return redirect(url)
