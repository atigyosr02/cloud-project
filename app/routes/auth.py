import time

import bcrypt
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_user, logout_user

from app.audit import log_action
from app.extensions import limiter
from app.models.db import fetch_one
from app.models.user import User

auth_bp = Blueprint("auth", __name__)
DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"invalid-login-password", bcrypt.gensalt())


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        row = fetch_one(
            "SELECT id, email, name, role, is_active, password_hash FROM users "
            "WHERE email = %s AND is_active = TRUE",
            (email,),
        )
        valid = False
        candidate_hash = row["password_hash"].encode("utf-8") if row else DUMMY_PASSWORD_HASH
        try:
            valid = bcrypt.checkpw(password.encode("utf-8"), candidate_hash) and row is not None
        except (ValueError, TypeError):
            valid = False
        if valid:
            session.clear()
            user = User(row)
            login_user(user, remember=False, fresh=True)
            session.permanent = True
            session["last_activity"] = time.time()
            log_action("Connexion")
            if user.role == "patient":
                return redirect(url_for("portal.patient_home"))
            return redirect(url_for("main.dashboard"))
        flash("Adresse e-mail ou mot de passe incorrect.", "danger")
    return render_template("login.html")


@auth_bp.post("/logout")
def logout():
    log_action("Déconnexion")
    logout_user()
    session.clear()
    flash("Vous êtes déconnecté(e).", "info")
    return redirect(url_for("auth.login"))