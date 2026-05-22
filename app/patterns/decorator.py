"""Patrón Decorator — filtros y ajustes encadenables.

La estructura sigue el diagrama UML:

    ImageComponent
        ^         ^
        |         |
    ImageLayer    FilterDecorator
                       ^
                       |
                  SepiaFilter / BrightnessFilter / ...

Cada filtro envuelve un `ImageComponent`. Al pedirle `render(image)` aplica
la transformación al resultado del componente envuelto, de modo que se
pueden encadenar tantos filtros como se quiera:

    pipeline = SepiaFilter(BrightnessFilter(ContrastFilter(base), 1.2), 1.0)
    pipeline.render(image)

Esto encaja perfecto con la idea de "sliders" del usuario:
    * El slider de brillo añade/edita un `BrightnessFilter` en la cadena.
    * Lo mismo para contraste, saturación, nitidez, viñeta, sepia, b/n,
      desenfoque, etc.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class ImageComponent(ABC):
    """Interfaz común — entrega una `PIL.Image` final."""

    @abstractmethod
    def render(self, base_image: Image.Image) -> Image.Image: ...


@dataclass
class BaseImageComponent(ImageComponent):
    """Componente concreto — simplemente devuelve la imagen tal cual."""

    def render(self, base_image: Image.Image) -> Image.Image:
        return base_image.copy()


class FilterDecorator(ImageComponent):
    """Decorador abstracto — guarda referencia a otro `ImageComponent`."""

    name: str = "filter"

    def __init__(self, wrapped: ImageComponent, value: float = 1.0) -> None:
        self.wrapped = wrapped
        self.value = value

    def render(self, base_image: Image.Image) -> Image.Image:
        intermediate = self.wrapped.render(base_image)
        return self._apply(intermediate)

    @abstractmethod
    def _apply(self, image: Image.Image) -> Image.Image: ...


class BrightnessFilter(FilterDecorator):
    name = "brightness"

    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageEnhance.Brightness(image).enhance(self.value)


class ContrastFilter(FilterDecorator):
    name = "contrast"

    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageEnhance.Contrast(image).enhance(self.value)


class SaturationFilter(FilterDecorator):
    name = "saturation"

    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageEnhance.Color(image).enhance(self.value)


class SharpnessFilter(FilterDecorator):
    name = "sharpness"

    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageEnhance.Sharpness(image).enhance(self.value)


class BlurFilter(FilterDecorator):
    name = "blur"

    def _apply(self, image: Image.Image) -> Image.Image:
        radius = max(0.0, float(self.value))
        if radius == 0:
            return image
        return image.filter(ImageFilter.GaussianBlur(radius=radius))


class SepiaFilter(FilterDecorator):
    """Sepia clásico — el ejemplo del diagrama UML."""

    name = "sepia"

    def _apply(self, image: Image.Image) -> Image.Image:
        strength = max(0.0, min(float(self.value), 1.0))
        if strength == 0:
            return image
        grayscale = ImageOps.grayscale(image).convert("RGB")
        sepia_palette = [
            (int(min(255, i * 1.07)), int(min(255, i * 0.74)), int(min(255, i * 0.43)))
            for i in range(256)
        ]
        sepia = Image.new("RGB", grayscale.size)
        sepia.putdata([sepia_palette[p[0]] for p in grayscale.getdata()])
        return Image.blend(image.convert("RGB"), sepia, strength)


class GrayscaleFilter(FilterDecorator):
    name = "grayscale"

    def _apply(self, image: Image.Image) -> Image.Image:
        strength = max(0.0, min(float(self.value), 1.0))
        if strength == 0:
            return image
        return Image.blend(image.convert("RGB"), ImageOps.grayscale(image).convert("RGB"), strength)


class InvertFilter(FilterDecorator):
    name = "invert"

    def _apply(self, image: Image.Image) -> Image.Image:
        if not self.value:
            return image
        return ImageOps.invert(image.convert("RGB"))


FILTER_REGISTRY: dict[str, type[FilterDecorator]] = {
    cls.name: cls
    for cls in (
        BrightnessFilter,
        ContrastFilter,
        SaturationFilter,
        SharpnessFilter,
        BlurFilter,
        SepiaFilter,
        GrayscaleFilter,
        InvertFilter,
    )
}


def build_pipeline(filters: list[dict[str, Any]]) -> ImageComponent:
    """Construye una cadena de decoradores a partir de su descripción JSON.

    `filters` es una lista de `{"name": "brightness", "value": 1.2}`. Los
    valores neutrales (1.0 para enhancers, 0 para blur/sepia/etc.) producen
    una imagen idéntica al original, por eso podemos guardar todos los
    sliders aunque estén en su valor neutro.
    """
    pipeline: ImageComponent = BaseImageComponent()
    for cfg in filters or []:
        name = cfg.get("name")
        if name not in FILTER_REGISTRY:
            continue
        pipeline = FILTER_REGISTRY[name](pipeline, value=float(cfg.get("value", 1.0)))
    return pipeline
