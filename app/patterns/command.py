"""Patrón Command — historia de acciones con undo / redo.

Cada acción del usuario se modela como un :class:`Command` con dos métodos:

* `execute()` aplica la mutación sobre el estado (DB).
* `undo()`   revierte exactamente esa mutación.

`CommandHistory` mantiene dos pilas (las "pending" y las "undone") y se
sincroniza con la tabla `HistoryEntry` para que el historial sobreviva a
recargas. Cuando se ejecuta una nueva acción tras un undo, las acciones
"redo-ables" se descartan, como en cualquier editor.
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any

from ..extensions import db
from ..models import HistoryEntry, Layer, Project
from .prototype import LayerPrototype, clone_from_layer


class Command(ABC):
    name: str = "command"

    def __init__(self, project: Project, payload: dict[str, Any]) -> None:
        self.project = project
        self.payload = payload
        self.inverse_payload: dict[str, Any] = {}

    @abstractmethod
    def execute(self) -> dict[str, Any]:
        """Aplica el cambio y devuelve datos útiles para el frontend."""

    @abstractmethod
    def undo(self) -> dict[str, Any]:
        """Revierte el cambio usando `self.inverse_payload`."""


# ─────────────────────────────────────────────────────────────────────────────
# Comandos concretos
# ─────────────────────────────────────────────────────────────────────────────


class AddShapeCommand(Command):
    """Añade una nueva capa de forma (círculo, rectángulo, estrella, ...)."""

    name = "add_shape"

    def execute(self) -> dict[str, Any]:
        max_z = max((l.z_index for l in self.project.layers), default=0)
        layer = Layer(
            project_id=self.project.id,
            kind="shape",
            z_index=max_z + 1,
            data=self.payload["data"],
        )
        db.session.add(layer)
        db.session.flush()
        self.inverse_payload = {"layer_id": layer.id}
        return {"layer": layer.to_dict()}

    def undo(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.inverse_payload["layer_id"])
        if layer is not None:
            db.session.delete(layer)
        return {"layer_id": self.inverse_payload["layer_id"]}


class CloneLayerCommand(Command):
    """Clona una capa existente usando el patrón Prototype."""

    name = "clone_layer"

    def execute(self) -> dict[str, Any]:
        source = db.session.get(Layer, self.payload["source_layer_id"])
        if source is None:
            raise ValueError("Capa origen no existe")
        proto: LayerPrototype = clone_from_layer(source)
        max_z = max((l.z_index for l in self.project.layers), default=0)
        new_layer = Layer(
            project_id=self.project.id,
            kind=proto.kind,
            z_index=max_z + 1,
            data=proto.data,
        )
        db.session.add(new_layer)
        db.session.flush()
        self.inverse_payload = {"layer_id": new_layer.id}
        return {"layer": new_layer.to_dict()}

    def undo(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.inverse_payload["layer_id"])
        if layer is not None:
            db.session.delete(layer)
        return {"layer_id": self.inverse_payload["layer_id"]}


class DeleteLayerCommand(Command):
    name = "delete_layer"

    def execute(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.payload["layer_id"])
        if layer is None or layer.project_id != self.project.id:
            raise ValueError("Capa no encontrada")
        self.inverse_payload = {
            "snapshot": {
                "id": layer.id,
                "kind": layer.kind,
                "z_index": layer.z_index,
                "data": copy.deepcopy(layer.data),
                "visible": layer.visible,
            }
        }
        db.session.delete(layer)
        return {"layer_id": layer.id}

    def undo(self) -> dict[str, Any]:
        snap = self.inverse_payload["snapshot"]
        restored = Layer(
            id=snap["id"],
            project_id=self.project.id,
            kind=snap["kind"],
            z_index=snap["z_index"],
            data=snap["data"],
            visible=snap["visible"],
        )
        db.session.add(restored)
        return {"layer": restored.to_dict()}


class UpdateLayerCommand(Command):
    """Mueve / redimensiona / re-colorea una capa.

    `payload["changes"]` es un dict con los campos de `data` a actualizar.
    Guardamos los valores previos para revertirlos.
    """

    name = "update_layer"

    def execute(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.payload["layer_id"])
        if layer is None:
            raise ValueError("Capa no encontrada")
        before: dict[str, Any] = {}
        new_data = copy.deepcopy(layer.data) or {}
        for key, value in self.payload["changes"].items():
            before[key] = new_data.get(key)
            new_data[key] = value
        layer.data = new_data
        self.inverse_payload = {"layer_id": layer.id, "before": before}
        return {"layer": layer.to_dict()}

    def undo(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.inverse_payload["layer_id"])
        if layer is None:
            return {}
        new_data = copy.deepcopy(layer.data) or {}
        for key, value in self.inverse_payload["before"].items():
            if value is None:
                new_data.pop(key, None)
            else:
                new_data[key] = value
        layer.data = new_data
        return {"layer": layer.to_dict()}


class ApplyFilterCommand(Command):
    """Aplica (o ajusta) un filtro decorator sobre una capa.

    El frontend envía: `{"layer_id": X, "filter": "brightness", "value": 1.2}`.
    Si el filtro ya existía, se actualiza su valor (y se guarda el valor
    previo); si no, se añade a la cadena.
    """

    name = "apply_filter"

    NEUTRAL_VALUES = {
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "sharpness": 1.0,
        "blur": 0.0,
        "sepia": 0.0,
        "grayscale": 0.0,
        "invert": 0.0,
    }

    def execute(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.payload["layer_id"])
        if layer is None:
            raise ValueError("Capa no encontrada")
        filter_name = self.payload["filter"]
        value = float(self.payload["value"])
        data = copy.deepcopy(layer.data) or {}
        filters: list[dict[str, Any]] = list(data.get("filters", []))

        previous_value: float | None = None
        existed = False
        for entry in filters:
            if entry.get("name") == filter_name:
                previous_value = float(entry.get("value", self.NEUTRAL_VALUES.get(filter_name, 1.0)))
                entry["value"] = value
                existed = True
                break
        if not existed:
            filters.append({"name": filter_name, "value": value})

        data["filters"] = filters
        layer.data = data
        self.inverse_payload = {
            "layer_id": layer.id,
            "filter": filter_name,
            "previous_value": previous_value,
            "existed": existed,
        }
        return {"layer": layer.to_dict()}

    def undo(self) -> dict[str, Any]:
        layer = db.session.get(Layer, self.inverse_payload["layer_id"])
        if layer is None:
            return {}
        data = copy.deepcopy(layer.data) or {}
        filters: list[dict[str, Any]] = list(data.get("filters", []))
        filter_name = self.inverse_payload["filter"]
        if self.inverse_payload["existed"]:
            for entry in filters:
                if entry.get("name") == filter_name:
                    entry["value"] = self.inverse_payload["previous_value"]
                    break
        else:
            filters = [f for f in filters if f.get("name") != filter_name]
        data["filters"] = filters
        layer.data = data
        return {"layer": layer.to_dict()}


# ─────────────────────────────────────────────────────────────────────────────
# Registro + invocador
# ─────────────────────────────────────────────────────────────────────────────


COMMAND_REGISTRY: dict[str, type[Command]] = {
    cls.name: cls
    for cls in (
        AddShapeCommand,
        CloneLayerCommand,
        DeleteLayerCommand,
        UpdateLayerCommand,
        ApplyFilterCommand,
    )
}


class CommandHistory:
    """Invocador que ejecuta comandos y mantiene la historia persistida."""

    def __init__(self, project: Project) -> None:
        self.project = project

    # ── ejecución de un comando nuevo ────────────────────────────────────
    def run(self, command: Command) -> dict[str, Any]:
        result = command.execute()

        # Si había historial "redo-able" después del último ejecutado, lo borramos.
        pending_redo = (
            HistoryEntry.query.filter_by(project_id=self.project.id, is_undone=True)
            .order_by(HistoryEntry.id.desc())
            .all()
        )
        for entry in pending_redo:
            db.session.delete(entry)

        entry = HistoryEntry(
            project_id=self.project.id,
            command_name=command.name,
            payload=command.payload,
            inverse_payload=command.inverse_payload,
            is_undone=False,
        )
        db.session.add(entry)
        db.session.commit()
        result["history_id"] = entry.id
        return result

    # ── undo / redo ──────────────────────────────────────────────────────
    def undo(self) -> dict[str, Any] | None:
        last = (
            HistoryEntry.query.filter_by(project_id=self.project.id, is_undone=False)
            .order_by(HistoryEntry.id.desc())
            .first()
        )
        if last is None:
            return None
        cmd_cls = COMMAND_REGISTRY.get(last.command_name)
        if cmd_cls is None:
            return None
        cmd = cmd_cls(self.project, last.payload)
        cmd.inverse_payload = last.inverse_payload
        result = cmd.undo()
        last.is_undone = True
        db.session.commit()
        return {"action": "undo", "command": last.command_name, "result": result}

    def redo(self) -> dict[str, Any] | None:
        nxt = (
            HistoryEntry.query.filter_by(project_id=self.project.id, is_undone=True)
            .order_by(HistoryEntry.id.asc())
            .first()
        )
        if nxt is None:
            return None
        cmd_cls = COMMAND_REGISTRY.get(nxt.command_name)
        if cmd_cls is None:
            return None
        cmd = cmd_cls(self.project, nxt.payload)
        result = cmd.execute()
        nxt.inverse_payload = cmd.inverse_payload
        nxt.is_undone = False
        db.session.commit()
        return {"action": "redo", "command": nxt.command_name, "result": result}

    def stats(self) -> dict[str, int]:
        pending = HistoryEntry.query.filter_by(project_id=self.project.id, is_undone=False).count()
        redoable = HistoryEntry.query.filter_by(project_id=self.project.id, is_undone=True).count()
        return {"undo_count": pending, "redo_count": redoable}
