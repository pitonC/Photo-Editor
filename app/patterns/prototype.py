"""Patrón Prototype.

Cada capa sabe clonarse a sí misma. Los clientes no necesitan saber qué
subclase concreta están clonando: piden `clone()` y reciben una capa nueva
con los mismos atributos, lista para colocarse en otra coordenada.

Esto demuestra el patrón tal como aparece en el diagrama UML:

    Prototype  <|.. ImageLayer
    Prototype  <|.. ShapeLayer

En el editor se usa para el "copy/paste" de formas (y opcionalmente de capas
de imagen): seleccionas una capa, pulsas duplicar y aparece otra idéntica
con un pequeño offset.
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any


class Prototype(ABC):
    @abstractmethod
    def clone(self) -> "Prototype":
        """Devuelve una copia profunda lista para insertarse."""


class LayerPrototype(Prototype):
    """Adaptador sobre el dict `data` de una capa.

    Mantenemos la lógica de clonado fuera del modelo SQLAlchemy para que
    `Layer` siga siendo un simple registro persistido. Aquí vive la regla
    de negocio del patrón.
    """

    OFFSET_PX = 24

    def __init__(self, kind: str, data: dict[str, Any], z_index: int) -> None:
        self.kind = kind
        self.data = data
        self.z_index = z_index

    def clone(self) -> "LayerPrototype":
        cloned_data = copy.deepcopy(self.data)
        if self.kind == "shape":
            cloned_data["x"] = cloned_data.get("x", 0) + self.OFFSET_PX
            cloned_data["y"] = cloned_data.get("y", 0) + self.OFFSET_PX
        elif self.kind == "image":
            cloned_data["x"] = cloned_data.get("x", 0) + self.OFFSET_PX
            cloned_data["y"] = cloned_data.get("y", 0) + self.OFFSET_PX
        return LayerPrototype(kind=self.kind, data=cloned_data, z_index=self.z_index + 1)


def clone_from_layer(layer) -> LayerPrototype:
    """Construye un :class:`LayerPrototype` a partir de un ORM `Layer` y lo clona."""
    proto = LayerPrototype(kind=layer.kind, data=layer.data, z_index=layer.z_index)
    return proto.clone()
