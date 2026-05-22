"""Servicio de composición final de la imagen.

Toma la imagen base + sus capas y aplica:
    1. El pipeline de filtros (Decorator) sobre la imagen base.
    2. Las capas de forma (círculo, rectángulo, estrella) encima.
    3. Filtros también sobre las formas si los tienen.

Devuelve la PIL.Image lista para servirse al cliente.
"""
from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

from flask import current_app
from PIL import Image, ImageDraw

from ..models import Project
from ..patterns.decorator import build_pipeline


def _shape_to_image(layer_data: dict[str, Any], canvas_size: tuple[int, int]) -> Image.Image:
    """Renderiza una forma como un PNG transparente del tamaño del canvas."""
    w, h = canvas_size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    kind = layer_data.get("type", "rect")
    color = layer_data.get("color", "#7c3aed")
    opacity = float(layer_data.get("opacity", 1.0))
    alpha = max(0, min(255, int(round(opacity * 255))))

    fill = _hex_to_rgba(color, alpha)
    x = int(layer_data.get("x", 0))
    y = int(layer_data.get("y", 0))
    width = int(layer_data.get("width", 200))
    height = int(layer_data.get("height", 200))

    if kind == "rect":
        radius = int(layer_data.get("radius", 24))
        draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=fill)
    elif kind == "circle":
        draw.ellipse((x, y, x + width, y + height), fill=fill)
    elif kind == "triangle":
        draw.polygon(
            [(x + width / 2, y), (x, y + height), (x + width, y + height)],
            fill=fill,
        )
    elif kind == "star":
        draw.polygon(_star_points(x, y, width, height), fill=fill)
    else:
        draw.rectangle((x, y, x + width, y + height), fill=fill)
    return img


def _star_points(x: int, y: int, w: int, h: int, points: int = 5) -> list[tuple[float, float]]:
    cx, cy = x + w / 2, y + h / 2
    outer = min(w, h) / 2
    inner = outer * 0.45
    coords: list[tuple[float, float]] = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        theta = (math.pi / points) * i - math.pi / 2
        coords.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return coords


def _hex_to_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def render_project(project: Project) -> Image.Image:
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    base_path = upload_dir / project.base_image_filename
    with Image.open(base_path) as raw:
        base = raw.convert("RGBA")
        if base.size != (project.width, project.height):
            base = base.resize((project.width, project.height))

    canvas_size = base.size
    composed = base

    base_layer = next((l for l in project.layers if l.kind == "image"), None)
    if base_layer is not None:
        filters = base_layer.data.get("filters", []) if base_layer.data else []
        pipeline = build_pipeline(filters)
        composed = pipeline.render(base).convert("RGBA")

    for layer in project.layers:
        if not layer.visible or layer.kind != "shape":
            continue
        shape_img = _shape_to_image(layer.data or {}, canvas_size)
        filters = (layer.data or {}).get("filters", [])
        if filters:
            shape_pipeline = build_pipeline(filters)
            shape_img = shape_pipeline.render(shape_img).convert("RGBA")
        composed = Image.alpha_composite(composed.convert("RGBA"), shape_img)

    return composed


def render_to_png_bytes(project: Project) -> bytes:
    img = render_project(project)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
