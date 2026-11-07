import uuid
from io import BytesIO
from xml.sax.saxutils import escape

from botocore.exceptions import BotoCoreError, ClientError
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.audit import execute_audited
from app.models.db import fetch_one
from app.routes.documents import ensure_bucket, s3_client
from app.security import role_required

prescriptions_bp = Blueprint(
    "prescriptions",
    __name__,
    url_prefix="/patients/<int:patient_id>/prescriptions",
)


def build_prescription_pdf(patient_name: str, doctor_name: str, medicines: str, instructions: str | None) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Ordonnance médicale - MediCare Cabinet",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("MediCare Cabinet - Ordonnance médicale", styles["Title"]),
        Spacer(1, 8 * mm),
        Paragraph(f"Patient : {escape(patient_name)}", styles["BodyText"]),
        Paragraph(f"Médecin : {escape(doctor_name)}", styles["BodyText"]),
        Spacer(1, 6 * mm),
        Paragraph("Médicaments et posologie", styles["Heading2"]),
    ]
    story.extend(Paragraph(escape(line), styles["BodyText"]) for line in medicines.splitlines())
    if instructions:
        story.extend(
            [
                Spacer(1, 5 * mm),
                Paragraph("Consignes complémentaires", styles["Heading2"]),
                Paragraph(escape(instructions).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    story.extend(
        [
            Spacer(1, 12 * mm),
            Paragraph("Document ajouté au dossier patient par le médecin.", styles["Italic"]),
        ]
    )
    document.build(story)
    return output.getvalue()

@prescriptions_bp.route("/new", methods=["GET", "POST"])
@role_required("medecin")
def create_prescription(patient_id: int):
    patient = fetch_one(
        "SELECT id, full_name FROM patients WHERE id = %s AND archived = FALSE",
        (patient_id,),
    )
    if not patient:
        abort(404)

    if request.method == "POST":
        medicines = "\n".join(
            line.strip()
            for line in request.form.get("medicines", "").splitlines()
            if line.strip()
        )
        instructions = request.form.get("instructions", "").strip() or None
        if not medicines or len(medicines) > 10000 or (instructions and len(instructions) > 3000):
            flash("La liste de médicaments est obligatoire. Vérifiez aussi la longueur des consignes.", "danger")
        else:
            pdf_content = build_prescription_pdf(
                patient["full_name"], current_user.name, medicines, instructions
            )
            object_key = f"documents/ordonnance-{uuid.uuid4()}.pdf"
            client = s3_client()
            ensure_bucket(client)
            put_options = {
                "Bucket": current_app.config["S3_BUCKET"],
                "Key": object_key,
                "Body": pdf_content,
                "ContentType": "application/pdf",
                "Metadata": {"patient-ref": str(patient_id), "document-kind": "ordonnance"},
            }
            if not current_app.config.get("S3_ENDPOINT_URL"):
                put_options["ServerSideEncryption"] = "AES256"
            client.put_object(**put_options)
            try:
                execute_audited(
                    "WITH new_prescription AS ("
                    "INSERT INTO prescriptions (patient_id, doctor_id, medicines, instructions) "
                    "VALUES (%s, %s, %s, %s) RETURNING id), "
                    "new_document AS ("
                    "INSERT INTO documents (patient_id, uploaded_by, object_key, label, file_type) "
                    "SELECT %s, %s, %s, %s, %s FROM new_prescription RETURNING patient_id) "
                    "SELECT patient_id FROM new_document",
                    (
                        patient_id,
                        int(current_user.id),
                        medicines,
                        instructions,
                        patient_id,
                        int(current_user.id),
                        object_key,
                        "Ordonnance médicale",
                        "application/pdf",
                    ),
                    "Création d'une ordonnance",
                    patient_id,
                    returning=True,
                )
            except Exception:
                try:
                    client.delete_object(Bucket=current_app.config["S3_BUCKET"], Key=object_key)
                except (BotoCoreError, ClientError):
                    pass
                raise
            flash("L’ordonnance a été ajoutée au dossier et son PDF est disponible dans les documents.", "success")
            return redirect(url_for("patients.patient_detail", patient_id=patient_id))

    return render_template("prescriptions/form.html", patient=patient)