import json
import logging
import time
from datetime import timedelta
from logging.config import dictConfig
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import limiter
from app.models.db import database_health
from app.models.user import User, get_user_by_id


class JsonFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


class SecureFlask(Flask):
    def log_exception(self, exc_info) -> None:
        self.logger.error("Unhandled request error")


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "json"}},
            "root": {"level": "INFO", "handlers": ["stdout"]},
        }
    )
    app = SecureFlask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY doit être défini dans l'environnement.")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.permanent_session_lifetime = timedelta(minutes=15)
    csrf = CSRFProtect()
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour continuer."
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return get_user_by_id(user_id)

    @app.before_request
    def enforce_idle_timeout() -> None:
        if current_user.is_authenticated:
            now = int(time.time())
            last_activity = session.get("last_activity", now)
            if now - last_activity >= 900:
                logout_user()
                session.clear()
                return
            session["last_activity"] = now
            session.permanent = True

    @app.after_request
    def set_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; "
            "script-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        if database_health():
            return jsonify(status="ok"), 200
        return jsonify(status="unavailable"), 503

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template("error.html", code=400, message="Formulaire expiré. Veuillez réessayer."), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="Accès non autorisé."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Cette page est introuvable."), 404

    @app.errorhandler(413)
    def request_too_large(_error):
        return render_template("error.html", code=413, message="Le fichier dépasse la taille maximale de 5 Mo."), 413

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("error.html", code=500, message="Une erreur interne est survenue."), 500

    from app.routes.admin import admin_bp
    from app.routes.appointments import appointments_bp
    from app.routes.auth import auth_bp
    from app.routes.consultations import consultations_bp
    from app.routes.documents import documents_bp
    from app.routes.main import main_bp
    from app.routes.patients import patients_bp
    from app.routes.portal import portal_bp
    from app.routes.prescriptions import prescriptions_bp

    for blueprint in (
        auth_bp,
        main_bp,
        patients_bp,
        consultations_bp,
        appointments_bp,
        documents_bp,
        admin_bp,
        portal_bp,
        prescriptions_bp,
    ):
        app.register_blueprint(blueprint)

    @app.context_processor
    def inject_year():
        from datetime import date

        return {"current_year": date.today().year}

    return app