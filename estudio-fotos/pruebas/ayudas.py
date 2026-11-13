"""Fotos y recortes de mentira para las pruebas (sin internet y sin el modelo real)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def imagen_foto(ancho: int = 1200, alto: int = 1200, producto: tuple[int, int, int] = (150, 70, 40)) -> Image.Image:
    """Una foto de producto inventada: fondo con degradado y un rectángulo de color en el centro."""
    y, x = np.mgrid[0:alto, 0:ancho]
    fondo = np.stack(
        [x * 200 // max(ancho - 1, 1) + 30, y * 180 // max(alto - 1, 1) + 40, np.full_like(x, 110)], axis=-1
    ).astype(np.uint8)
    fondo[alto // 5 : alto * 4 // 5, ancho // 4 : ancho * 3 // 4] = producto
    return Image.fromarray(fondo, "RGB")


def foto(ancho: int = 1200, alto: int = 1200, formato: str = "JPEG", **opciones) -> bytes:
    """Los bytes de una foto inventada en JPEG, PNG o WEBP."""
    memoria = io.BytesIO()
    imagen_foto(ancho, alto).save(memoria, formato, **opciones)
    return memoria.getvalue()


def recorte(ancho: int, alto: int, caja: tuple[int, int, int, int], forma: str = "rectangulo",
            color: tuple[int, int, int] = (150, 70, 40)) -> Image.Image:
    """Un recorte inventado: transparente, con un producto opaco que llena exactamente `caja`."""
    izquierda, arriba, derecha, abajo = caja
    datos = np.zeros((alto, ancho, 4), dtype=np.uint8)
    if forma == "elipse":
        y, x = np.mgrid[arriba:abajo, izquierda:derecha]
        centro_x, centro_y = (izquierda + derecha - 1) / 2, (arriba + abajo - 1) / 2
        radio_x, radio_y = (derecha - izquierda) / 2, (abajo - arriba) / 2
        dentro = ((x - centro_x) / radio_x) ** 2 + ((y - centro_y) / radio_y) ** 2 <= 1
        zona = datos[arriba:abajo, izquierda:derecha]
        zona[dentro] = (*color, 255)
    else:
        datos[arriba:abajo, izquierda:derecha] = (*color, 255)
    # Un poco de textura, para que el JPEG pese como una foto y no como un dibujo plano.
    ruido = np.random.default_rng(7).integers(-18, 18, size=(alto, ancho, 1))
    visible = datos[..., 3:4] > 0
    datos[..., :3] = np.where(visible, np.clip(datos[..., :3].astype(np.int16) + ruido, 0, 255), 0).astype(np.uint8)
    return Image.fromarray(datos, "RGBA")


def caja_no_blanca(imagen: Image.Image, umbral: int = 250) -> tuple[int, int, int, int]:
    """El rectángulo que ocupa todo lo que no es (casi) blanco: así se mide el producto en un archivo exportado."""
    datos = np.asarray(imagen.convert("RGB"))
    producto = (datos < umbral).any(axis=2)
    filas = np.flatnonzero(producto.any(axis=1))
    columnas = np.flatnonzero(producto.any(axis=0))
    return int(columnas[0]), int(filas[0]), int(columnas[-1]) + 1, int(filas[-1]) + 1
