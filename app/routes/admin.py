import re

import bcrypt
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_action
from app.models.db import execute, fetch_all, fetch_one
from app.security import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/logs")
@role_required("admin")
def audit_logs():
    page = max(request.args.get("page", 1, type=int), 1)
    logs = fetch_all(
        "SELECT l.created_at, l.action, l.details, l.ip_address, u.name AS user_name, "
        "p.full_name AS patient_name FROM audit_logs l LEFT JOIN users u ON u.id = l.user_id "
        "LEFT JOIN patients p ON p.id = l.patient_id ORDER BY l.created_at DESC LIMIT %s OFFSET %s",
        (50, (page - 1) * 50),
    )
    return render_template("admin/logs.html", logs=logs, page=page)


@admin_bp.get("/users")
@role_required("admin")
def users():
    rows = fetch_all("SELECT id, name, email, role, is_active, created_at FROM users ORDER BY name")
    return render_template("admin/users.html", users=rows)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@role_required("admin")
def create_user():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        email = request.form.get("email", "").strip().lower()[:254]
        role = request.form.get("role", "")
        password = request.form.get("password", "")
        if role not in {"admin", "medecin", "secretaire"} or not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Veuillez vérifier les informations du compte.", "danger")
        elif len(password) < 8 or len(password.encode("utf-8")) > 72 or not re.search(r"\d", password):
            flash("Le mot de passe doit comporter 8 à 72 octets et au moins un chiffre.", "danger")
        elif fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
            flash("Cette adresse e-mail est déjà utilisée.", "danger")
        else:
            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            execute(
                "INSERT INTO users (name, email, role, password_hash) VALUES (%s, %s, %s, %s)",
                (name, email, role, password_hash),
            )
            log_action("Création d'un utilisateur")
            flash("Le compte a été créé.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html")


@admin_bp.post("/users/<int:user_id>/deactivate")
@role_required("admin")
def deactivate_user(user_id: int):
    if str(user_id) == str(current_user.id):
        flash("Vous ne pouvez pas désactiver votre propre compte.", "danger")
        return redirect(url_for("admin.users"))
    changed = execute("UPDATE users SET is_active = FALSE WHERE id = %s AND is_active = TRUE", (user_id,))
    if not changed:
        abort(404)
    log_action("Désactivation d'un utilisateur")
    flash("Le compte a été désactivé.", "success")
    return redirect(url_for("admin.users"))