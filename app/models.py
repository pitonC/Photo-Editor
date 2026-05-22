"""Modelos SQLAlchemy — la capa "Model" del patrón MVC/MTV.

Diseño:
    Project    1 ──< N  Layer
    Project    1 ──< N  HistoryEntry

* `Project`      representa una edición (la foto base + sus capas).
* `Layer`        es polimórfica: puede ser una capa de imagen o una forma.
                 Su atributo `data` (JSON) almacena la información concreta
                 (pixeles, tipo, color, filtros aplicados, posición, etc.).
* `HistoryEntry` registra los `Command` ejecutados para soportar undo/redo
                 incluso después de recargar la página.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import JSON

from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Project(TimestampMixin, db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, default="Untitled")
    base_image_filename = db.Column(db.String(255), nullable=False)
    width = db.Column(db.Integer, nullable=False, default=1024)
    height = db.Column(db.Integer, nullable=False, default=1024)

    layers = db.relationship(
        "Layer",
        backref="project",
        cascade="all, delete-orphan",
        order_by="Layer.z_index",
    )
    history = db.relationship(
        "HistoryEntry",
        backref="project",
        cascade="all, delete-orphan",
        order_by="HistoryEntry.id",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "base_image": self.base_image_filename,
            "width": self.width,
            "height": self.height,
            "layers": [layer.to_dict() for layer in self.layers],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Layer(TimestampMixin, db.Model):
    """Capa de un proyecto.

    `kind` controla qué tipo de capa es: "image" o "shape".
    `data` es un JSON con la configuración específica:

    * image -> { "source": "<filename>", "opacity": 1.0,
                 "filters": [ {"name": "brightness", "value": 1.2}, ... ] }
    * shape -> { "type": "circle" | "rect" | "star",
                 "color": "#ff0080", "x": 100, "y": 50,
                 "width": 200, "height": 200, "rotation": 0,
                 "opacity": 1.0, "filters": [...] }
    """

    __tablename__ = "layers"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    z_index = db.Column(db.Integer, nullable=False, default=0)
    data = db.Column(JSON, nullable=False, default=dict)
    visible = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "z_index": self.z_index,
            "data": self.data,
            "visible": self.visible,
        }


class HistoryEntry(db.Model):
    """Registro de comandos ejecutados (para undo/redo persistente)."""

    __tablename__ = "history_entries"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    command_name = db.Column(db.String(60), nullable=False)
    payload = db.Column(JSON, nullable=False, default=dict)
    inverse_payload = db.Column(JSON, nullable=False, default=dict)
    is_undone = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def serialize(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "command": self.command_name,
                "payload": self.payload,
                "inverse": self.inverse_payload,
                "is_undone": self.is_undone,
            }
        )
