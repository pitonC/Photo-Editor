"""API JSON usada por el editor (sliders, formas, undo/redo, render).

Cada endpoint es un *Cliente* del patrón Command: construye el comando
adecuado y se lo pasa al `CommandHistory` (el Invocador).
"""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, request, send_file
from io import BytesIO

from ..extensions import db
from ..models import Project
from ..patterns.command import (
    AddShapeCommand,
    ApplyFilterCommand,
    CloneLayerCommand,
    CommandHistory,
    DeleteLayerCommand,
    UpdateLayerCommand,
)
from ..services.renderer import render_to_png_bytes

bp = Blueprint("api", __name__)


def _get_project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None:
        abort(404)
    return project


@bp.route("/projects/<int:project_id>")
def project_state(project_id: int):
    project = _get_project(project_id)
    history = CommandHistory(project)
    return jsonify({"project": project.to_dict(), "history": history.stats()})


@bp.route("/projects/<int:project_id>/render")
def project_render(project_id: int):
    project = _get_project(project_id)
    png_bytes = render_to_png_bytes(project)
    return send_file(BytesIO(png_bytes), mimetype="image/png", max_age=0)


@bp.route("/projects/<int:project_id>/commands/apply_filter", methods=["POST"])
def apply_filter(project_id: int):
    project = _get_project(project_id)
    payload = request.get_json(force=True) or {}
    command = ApplyFilterCommand(project, payload)
    result = CommandHistory(project).run(command)
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/commands/add_shape", methods=["POST"])
def add_shape(project_id: int):
    project = _get_project(project_id)
    payload = request.get_json(force=True) or {}
    command = AddShapeCommand(project, payload)
    result = CommandHistory(project).run(command)
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/commands/clone_layer", methods=["POST"])
def clone_layer(project_id: int):
    project = _get_project(project_id)
    payload = request.get_json(force=True) or {}
    command = CloneLayerCommand(project, payload)
    result = CommandHistory(project).run(command)
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/commands/delete_layer", methods=["POST"])
def delete_layer(project_id: int):
    project = _get_project(project_id)
    payload = request.get_json(force=True) or {}
    command = DeleteLayerCommand(project, payload)
    result = CommandHistory(project).run(command)
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/commands/update_layer", methods=["POST"])
def update_layer(project_id: int):
    project = _get_project(project_id)
    payload = request.get_json(force=True) or {}
    command = UpdateLayerCommand(project, payload)
    result = CommandHistory(project).run(command)
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/undo", methods=["POST"])
def undo(project_id: int):
    project = _get_project(project_id)
    result = CommandHistory(project).undo()
    if result is None:
        return jsonify({"ok": False, "reason": "nothing-to-undo"}), 200
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})


@bp.route("/projects/<int:project_id>/redo", methods=["POST"])
def redo(project_id: int):
    project = _get_project(project_id)
    result = CommandHistory(project).redo()
    if result is None:
        return jsonify({"ok": False, "reason": "nothing-to-redo"}), 200
    return jsonify({"ok": True, "result": result, "history": CommandHistory(project).stats()})
