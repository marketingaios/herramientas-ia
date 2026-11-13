"""Fondo blanco puro, encuadre y medidas de cada plataforma.

Nunca se añade texto, logo, borde, sombra ni marca de agua: solo el producto sobre blanco 255, 255, 255.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile

from .plataformas import Plataforma, texto_peso
from .subidas import numero, perfil_srgb

UMBRAL_PRODUCTO = 13  # alfa mínimo (un 5 %) para contar un píxel como producto
CALIDAD = 90  # calidad JPEG de partida; baja si el archivo supera el peso de la plataforma
CALIDAD_MINIMA = 30
MARGEN_JPEG = 8  # píxeles alrededor del producto donde la compresión JPEG puede no ser blanco exacto
SUBMUESTREO = 0  # 4:4:4: el color no se emborrona en los bordes ni en el texto de las etiquetas


class SinProducto(Exception):
    """El recorte no tiene ningún píxel de producto."""


@dataclass(frozen=True)
class Encuadre:
    ancho: int  # medida del lienzo
    alto: int
    producto: tuple[int, int]  # medida del producto dentro del lienzo
    posicion: tuple[int, int]  # esquina superior izquierda del producto
    escala: float  # cuánto se amplió (>1) o redujo (<1) el producto

    @property
    def porcentaje(self) -> float:
        """Cuánto ocupa el producto, en la dimensión que más llena."""
        return max(self.producto[0] / self.ancho, self.producto[1] / self.alto) * 100


@dataclass
class Salida:
    archivo: str
    plataforma: str  # id
    nombre_plataforma: str
    ancho: int
    alto: int
    peso: int  # bytes
    porcentaje: float
    escala: float
    calidad: int
    avisos: list[str] = field(default_factory=list)
    ruta: Path | None = None

    @property
    def medida(self) -> str:
        return f"{self.ancho}x{self.alto}"


def caja_producto(alfa: np.ndarray) -> tuple[int, int, int, int] | None:
    """El rectángulo (izquierda, arriba, derecha, abajo) que contiene el producto."""
    visible = alfa >= UMBRAL_PRODUCTO
    filas = np.flatnonzero(visible.any(axis=1))
    columnas = np.flatnonzero(visible.any(axis=0))
    if filas.size == 0 or columnas.size == 0:
        return None
    return int(columnas[0]), int(filas[0]), int(columnas[-1]) + 1, int(filas[-1]) + 1


def calcular_encuadre(ancho_producto: int, alto_producto: int, plataforma: Plataforma) -> Encuadre:
    """La medida del lienzo y dónde va el producto: entero, centrado y ocupando el porcentaje de la plataforma.

    El producto cabe en la caja porcentaje×ancho por porcentaje×alto. En un lienzo cuadrado eso es lo mismo que
    «el lado más largo del producto ocupa el porcentaje».
    """
    proporcion = plataforma.porcentaje / 100
    ancho, alto = plataforma.ancho, plataforma.alto
    escala = min(proporcion * ancho / ancho_producto, proporcion * alto / alto_producto)

    if plataforma.sin_ampliar and escala > 1:
        # Amazon pide no agrandar las fotos pequeñas: la medida baja hasta la que no amplía el producto,
        # sin pasar del mínimo.
        ancho_minimo = plataforma.ancho_minimo or ancho
        alto_minimo = plataforma.alto_minimo or alto
        factor = max(1 / escala, ancho_minimo / ancho, alto_minimo / alto)
        ancho = max(ancho_minimo, min(ancho, math.floor(ancho * factor + 1e-9)))
        alto = max(alto_minimo, min(alto, math.floor(alto * factor + 1e-9)))
        escala = min(proporcion * ancho / ancho_producto, proporcion * alto / alto_producto)

    producto = (
        max(1, min(ancho, round(ancho_producto * escala))),
        max(1, min(alto, round(alto_producto * escala))),
    )
    posicion = ((ancho - producto[0]) // 2, (alto - producto[1]) // 2)
    return Encuadre(ancho=ancho, alto=alto, producto=producto, posicion=posicion, escala=escala)


def componer(recorte: Image.Image, plataforma: Plataforma) -> tuple[Image.Image, Encuadre]:
    """El producto del recorte sobre un lienzo blanco puro, con la medida de la plataforma."""
    recorte = recorte.convert("RGBA")
    alfa = np.asarray(recorte.getchannel("A"))
    caja = caja_producto(alfa)
    if caja is None:
        raise SinProducto()

    encuadre = calcular_encuadre(caja[2] - caja[0], caja[3] - caja[1], plataforma)

    trozo = recorte.crop(caja)
    limpio = np.array(trozo)
    limpio[limpio[..., 3] < UMBRAL_PRODUCTO] = 0  # fuera la neblina: lo que no es producto queda transparente
    # Con el color premultiplicado por el alfa, cambiar de medida no arrastra el color del fondo a los bordes.
    trozo = Image.fromarray(limpio, "RGBA").convert("RGBa")
    if trozo.size != encuadre.producto:
        trozo = trozo.resize(encuadre.producto, Image.Resampling.LANCZOS)

    datos = np.asarray(trozo).astype(np.int16)
    opacidad = datos[..., 3:4]
    color = datos[..., :3]
    opacidad = np.where(opacidad <= 3, 0, opacidad)  # el eco del filtro de reducción no debe manchar el blanco
    color = np.where(opacidad == 0, 0, color)
    # color premultiplicado + blanco × (1 − alfa) = color + (255 − alfa): donde no hay producto, 255 exacto.
    mezcla = np.clip(color + (255 - opacidad), 0, 255).astype(np.uint8)

    lienzo = np.full((encuadre.alto, encuadre.ancho, 3), 255, dtype=np.uint8)
    x, y = encuadre.posicion
    lienzo[y : y + encuadre.producto[1], x : x + encuadre.producto[0]] = mezcla
    return Image.fromarray(lienzo, "RGB"), encuadre


def fondo_es_blanco(imagen: Image.Image, encuadre: Encuadre) -> bool:
    """¿Todo lo que queda fuera del producto (con un margen para la compresión) es 255, 255, 255?"""
    datos = np.array(imagen.convert("RGB"))
    x, y = encuadre.posicion
    izquierda, arriba = max(0, x - MARGEN_JPEG), max(0, y - MARGEN_JPEG)
    derecha = min(encuadre.ancho, x + encuadre.producto[0] + MARGEN_JPEG)
    abajo = min(encuadre.alto, y + encuadre.producto[1] + MARGEN_JPEG)
    datos[arriba:abajo, izquierda:derecha] = 255
    return bool(datos.min() == 255)


def codificar_jpeg(imagen: Image.Image, encuadre: Encuadre, peso_maximo: int | None) -> tuple[bytes, int, bool, bool]:
    """JPEG en sRGB con calidad 90, que baja si el archivo supera el peso.

    Devuelve (datos, calidad, cabe en el peso, el fondo quedó blanco puro).
    """
    datos, calidad, blanco = b"", CALIDAD, True
    for calidad_base in range(CALIDAD, CALIDAD_MINIMA - 1, -5):
        datos, calidad, blanco = _codificar(imagen, encuadre, calidad_base)
        if peso_maximo is None or len(datos) <= peso_maximo:
            return datos, calidad, True, blanco
    return datos, calidad, False, blanco


def _codificar(imagen: Image.Image, encuadre: Encuadre, calidad_base: int) -> tuple[bytes, int, bool]:
    """Guarda y vuelve a abrir: si la compresión dejó el blanco en 254, prueba con la calidad de al lado."""
    datos, calidad = b"", calidad_base
    # Pillow reserva para el JPEG optimizado un búfer del tamaño de la imagen: con una foto muy difícil de
    # comprimir se queda corto y falla al guardar. Le damos sitio de sobra.
    ImageFile.MAXBLOCK = max(ImageFile.MAXBLOCK, imagen.width * imagen.height * 4 + 1_048_576)
    for ajuste in range(5):
        calidad = calidad_base - ajuste
        memoria = io.BytesIO()
        imagen.save(
            memoria, "JPEG", quality=calidad, subsampling=SUBMUESTREO, optimize=True, icc_profile=perfil_srgb()
        )
        datos = memoria.getvalue()
        with Image.open(io.BytesIO(datos)) as guardada:
            if fondo_es_blanco(guardada, encuadre):
                return datos, calidad, True
    return datos, calidad, False


def nombre_archivo(foto: str, plataforma: Plataforma, encuadre: Encuadre) -> str:
    return f"{foto}_{plataforma.id}_{encuadre.ancho}x{encuadre.alto}.jpg"


def exportar(recorte: Image.Image, foto: str, plataforma: Plataforma, carpeta: Path) -> Salida:
    """Crea el archivo de una foto para una plataforma y devuelve sus datos para el resumen."""
    imagen, encuadre = componer(recorte, plataforma)
    datos, calidad, cabe, blanco = codificar_jpeg(imagen, encuadre, plataforma.peso_maximo_bytes)

    avisos: list[str] = []
    if plataforma.sin_ampliar and encuadre.escala > 1.001:
        avisos.append(
            f"ampliada ×{_factor(encuadre.escala)}: {plataforma.nombre} pide no agrandar las fotos pequeñas"
        )
    elif encuadre.escala > 2:
        avisos.append(f"ampliada ×{_factor(encuadre.escala)}, puede verse borrosa")
    if not cabe:
        avisos.append(
            f"pesa {math.ceil(len(datos) / 1000)} KB: no se pudo bajar al máximo de {plataforma.nombre} "
            f"({texto_peso(plataforma.peso_maximo_kb)})"
        )
    if not blanco:
        avisos.append("el fondo no quedó blanco puro en todo el archivo: revísalo")

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = nombre_archivo(foto, plataforma, encuadre)
    ruta = carpeta / archivo
    ruta.write_bytes(datos)
    return Salida(
        archivo=archivo,
        plataforma=plataforma.id,
        nombre_plataforma=plataforma.nombre,
        ancho=encuadre.ancho,
        alto=encuadre.alto,
        peso=len(datos),
        porcentaje=round(encuadre.porcentaje, 1),
        escala=encuadre.escala,
        calidad=calidad,
        avisos=avisos,
        ruta=ruta,
    )


def _factor(escala: float) -> str:
    return numero(escala, 2 if escala < 1.1 else 1)
