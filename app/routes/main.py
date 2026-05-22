"""Vistas HTML (parte "V" / "Controller" del MVC en Flask MTV).

Estas funciones reciben el HTTP request, delegan en los modelos y servicios,
y renderizan los templates Jinja. Cada función es un *controlador*: nunca
contiene lógica de negocio profunda, solo orquesta.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Layer, Project

bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/")
def index():
    projects = Project.query.order_by(Project.updated_at.desc()).all()
    return render_template("index.html", projects=projects)


@bp.route("/projects", methods=["POST"])
def create_project():
    file = request.files.get("image")
    name = request.form.get("name", "Untitled").strip() or "Untitled"

    if file is None or file.filename == "":
        flash("Selecciona una imagen para empezar.", "error")
        return redirect(url_for("main.index"))
    if not _allowed(file.filename):
        flash("Formato no soportado. Usa PNG, JPG, JPEG, WEBP o BMP.", "error")
        return redirect(url_for("main.index"))

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Normalizamos todas las subidas a PNG/RGBA: así soportamos JPG, WEBP, etc.
    # de entrada, pero internamente trabajamos siempre con un único formato que
    # sí soporta transparencia (necesario para componer formas encima).
    stored_name = secure_filename(f"{uuid.uuid4().hex}.png")
    save_path = upload_dir / stored_name

    try:
        with Image.open(file.stream) as img:
            img = img.convert("RGBA")
            width, height = img.size
            max_side = 1600
            if max(width, height) > max_side:
                scale = max_side / max(width, height)
                width = int(width * scale)
                height = int(height * scale)
                img = img.resize((width, height), Image.LANCZOS)
            img.save(save_path, format="PNG", optimize=True)
    except UnidentifiedImageError:
        flash("No pudimos leer esa imagen. Prueba con PNG o JPG estándar.", "error")
        return redirect(url_for("main.index"))

    project = Project(
        name=name,
        base_image_filename=stored_name,
        width=width,
        height=height,
    )
    db.session.add(project)
    db.session.flush()

    base_layer = Layer(
        project_id=project.id,
        kind="image",
        z_index=0,
        data={
            "source": stored_name,
            "opacity": 1.0,
            "filters": [],
        },
    )
    db.session.add(base_layer)
    db.session.commit()

    return redirect(url_for("main.editor", project_id=project.id))


@bp.route("/editor/<int:project_id>")
def editor(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    return render_template("editor.html", project=project)


@bp.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    image_path = Path(current_app.config["UPLOAD_FOLDER"]) / project.base_image_filename
    db.session.delete(project)
    db.session.commit()
    try:
        image_path.unlink(missing_ok=True)
    except OSError:
        pass
    flash("Proyecto eliminado.", "ok")
    return redirect(url_for("main.index"))
