from typing import Any

from flask import request
from flask_login import current_user

from app.models.db import execute, get_db


def log_action(action: str, patient_id: int | None = None, details: str | None = None) -> None:
    user_id = current_user.get_id() if current_user.is_authenticated else None
    execute(
        "INSERT INTO audit_logs (user_id, patient_id, action, details, ip_address) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, patient_id, action[:100], details[:200] if details else None, request.remote_addr),
    )


def execute_audited(
    sql: str,
    params: tuple[Any, ...],
    action: str,
    patient_id: int | None,
    returning: bool = False,
) -> dict[str, Any] | None:
    user_id = current_user.get_id() if current_user.is_authenticated else None
    with get_db() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        result = cursor.fetchone() if returning else None
        audit_patient_id = result[0] if returning and result else patient_id
        cursor.execute(
            "INSERT INTO audit_logs (user_id, patient_id, action, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, audit_patient_id, action[:100], request.remote_addr),
        )
        if result is not None:
            return {"id": result[0]}
    return None