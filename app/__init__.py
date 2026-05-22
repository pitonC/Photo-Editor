"""Application factory.

Aquí vive la pieza "View/Controller" del patrón MVC (que en Flask se conoce
como MTV: Model–Template–View). El factory cablea los tres componentes:

* Model       -> `app.models` (SQLAlchemy)
* Template    -> `app/templates/*.html` (Jinja2)
* View (ctrl) -> `app.routes` (los blueprints reciben requests y deciden qué
                                modelo y template usar)
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .extensions import db


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    base_dir = Path(app.root_path).parent
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = Path(app.root_path) / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{instance_dir / 'photo_editor.sqlite3'}",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(upload_dir),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    if config:
        app.config.update(config)

    db.init_app(app)

    from . import models  # noqa: F401 — registra los modelos en SQLAlchemy
    from .routes.main import bp as main_bp
    from .routes.api import bp as api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()

    return app
