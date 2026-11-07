import uuid

import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.audit import log_action
from app.models.db import execute, fetch_one
from app.security import role_required

documents_bp = Blueprint("documents", __name__, url_prefix="/patients/<int:patient_id>/documents")
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED = {
    "pdf": ("application/pdf", b"%PDF-"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def s3_client(presigned: bool = False):
    options = {"region_name": current_app.config["AWS_REGION"]}
    endpoint_url = (
        current_app.config.get("S3_PUBLIC_ENDPOINT_URL") if presigned else None
    ) or current_app.config.get("S3_ENDPOINT_URL")
    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    if current_app.config.get("S3_ENDPOINT_URL"):
        options["aws_access_key_id"] = current_app.config.get("S3_ACCESS_KEY")
        options["aws_secret_access_key"] = current_app.config.get("S3_SECRET_KEY")
    return boto3.client("s3", **options)


def ensure_bucket(client) -> None:
    bucket = current_app.config["S3_BUCKET"]
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        if not current_app.config.get("S3_ENDPOINT_URL"):
            raise
        if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") not in {404, 301, 403}:
            raise
        try:
            client.create_bucket(Bucket=bucket)
        except ClientError as create_error:
            code = create_error.response.get("Error", {}).get("Code")
            if code not in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                raise


@documents_bp.post("")
@role_required("medecin")
def upload_document(patient_id: int):
    if not fetch_one("SELECT id FROM patients WHERE id = %s AND archived = FALSE", (patient_id,)):
        abort(404)
    uploaded = request.files.get("document")
    if not uploaded or not uploaded.filename or "." not in uploaded.filename:
        flash("Sélectionnez un document PDF, PNG ou JPG.", "danger")
        return redirect(url_for("patients.patient_detail", patient_id=patient_id))
    extension = uploaded.filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED:
        abort(400)
    content = uploaded.stream.read(MAX_FILE_SIZE + 1)
    content_type, signature = ALLOWED[extension]
    if len(content) > MAX_FILE_SIZE or not content.startswith(signature):
        abort(400)
    object_key = f"documents/{uuid.uuid4()}.{extension}"
    label = secure_filename(uploaded.filename)[:120] or "Document médical"
    client = s3_client(presigned=True)
    ensure_bucket(client)
    put_options = {
        "Bucket": current_app.config["S3_BUCKET"],
        "Key": object_key,
        "Body": content,
        "ContentType": content_type,
        "Metadata": {"patient-ref": str(patient_id)},
    }
    if not current_app.config.get("S3_ENDPOINT_URL"):
        put_options["ServerSideEncryption"] = "AES256"
    client.put_object(**put_options)
    execute(
        "INSERT INTO documents (patient_id, uploaded_by, object_key, label, file_type) "
        "VALUES (%s, %s, %s, %s, %s)",
        (patient_id, int(current_user.id), object_key, label, content_type),
    )
    log_action("Ajout d'un document médical", patient_id)
    flash("Le document a été ajouté.", "success")
    return redirect(url_for("patients.patient_detail", patient_id=patient_id))


@documents_bp.get("/<int:document_id>/download")
@role_required("medecin")
def download_document(patient_id: int, document_id: int):
    document = fetch_one(
        "SELECT id, object_key, file_type FROM documents WHERE id = %s AND patient_id = %s",
        (document_id, patient_id),
    )
    if not document:
        abort(404)
    log_action("Téléchargement d'un document médical", patient_id)
    client = s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": current_app.config["S3_BUCKET"], "Key": document["object_key"]},
        ExpiresIn=60,
    )
    return redirect(url)