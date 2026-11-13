"""Los ajustes del negocio, sin la clave: `estudio-fotos/ajustes.json` y el logo.

La clave de OpenRouter NO está aquí: vive solo en `.env` (ver `clave.py`).
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import unicodedata
import warnings
from pathlib import Path

from PIL import Image

from . import costos, equipo
from .subidas import MAX_MEGAPIXELES, detectar_tipo, numero

POR_DEFECTO = {
    "negocio": {"nombre": "", "color_principal": "#1F2937", "color_acento": "#0E9F6E"},
    "calidad_recorte": "automatica",
    "modelo_escenas": costos.MODELO_POR_DEFECTO,
    "tope_sesion_usd": costos.TOPE_POR_DEFECTO_USD,
}

NOMBRE_MAXIMO = 60
LOGO_MAX_MB = 5
LOGO_LADO = 600
_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")

MENSAJE_COLOR = "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."
MENSAJE_LOGO_FORMATO = "El logo debe ser una imagen JPG, PNG o WEBP."
MENSAJE_LOGO_DANADO = "No se puede abrir este logo: puede estar dañado."


class ErrorAjustes(Exception):
    """Un ajuste no vale; el mensaje dice qué corregir."""


def cargar(ruta: Path) -> dict:
    """Los ajustes guardados sobre los de fábrica. Un archivo roto o un valor raro no impide arrancar."""
    ajustes = copy.deepcopy(POR_DEFECTO)
    try:
        guardados = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ajustes
    if not isinstance(guardados, dict):
        return ajustes
    for campo in ("negocio", "calidad_recorte", "modelo_escenas", "tope_sesion_usd"):
        if campo in guardados:
            try:
                ajustes = aplicar(ajustes, {campo: guardados[campo]})
            except ErrorAjustes:
                pass  # ese valor se queda como de fábrica
    return ajustes


def guardar(ruta: Path, ajustes: dict) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.name}.tmp-{os.getpid()}")
    temporal.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def aplicar(actuales: dict, cambios: object) -> dict:
    """Los ajustes con los cambios pedidos, ya comprobados. Lo que no viene en `cambios` no se toca."""
    if not isinstance(cambios, dict):
        raise ErrorAjustes("Los ajustes no tienen la forma esperada.")
    nuevos = copy.deepcopy(actuales)

    negocio = cambios.get("negocio")
    if negocio is not None:
        if not isinstance(negocio, dict):
            raise ErrorAjustes("Los datos del negocio no tienen la forma esperada.")
        if "nombre" in negocio:
            nuevos["negocio"]["nombre"] = _nombre(negocio["nombre"])
        for campo in ("color_principal", "color_acento"):
            if campo in negocio:
                nuevos["negocio"][campo] = _color(negocio[campo])

    if "calidad_recorte" in cambios:
        if cambios["calidad_recorte"] not in equipo.CALIDADES:
            raise ErrorAjustes("La calidad del recorte debe ser Automática, Máxima o Rápida.")
        nuevos["calidad_recorte"] = cambios["calidad_recorte"]

    if "modelo_escenas" in cambios:
        if cambios["modelo_escenas"] not in costos.IDS_MODELOS:
            raise ErrorAjustes("Ese modelo de escenas no está en la lista.")
        nuevos["modelo_escenas"] = cambios["modelo_escenas"]

    if "tope_sesion_usd" in cambios:
        nuevos["tope_sesion_usd"] = _tope(cambios["tope_sesion_usd"])
    return nuevos


def _nombre(valor: object) -> str:
    if not isinstance(valor, str):
        raise ErrorAjustes("El nombre del negocio debe ser un texto.")
    limpio = "".join(c for c in valor if unicodedata.category(c)[0] != "C")  # fuera caracteres de control
    limpio = " ".join(limpio.split())
    if len(limpio) > NOMBRE_MAXIMO:
        raise ErrorAjustes(f"El nombre del negocio puede tener hasta {NOMBRE_MAXIMO} caracteres.")
    return limpio


def _color(valor: object) -> str:
    if not isinstance(valor, str) or not _COLOR.fullmatch(valor):
        raise ErrorAjustes(MENSAJE_COLOR)
    return valor.upper()


def _tope(valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ErrorAjustes("El tope de gasto debe ser un número, por ejemplo 1.")
    if not 0 <= valor <= costos.TOPE_MAXIMO_USD:
        raise ErrorAjustes(f"El tope de gasto debe estar entre 0 y {costos.TOPE_MAXIMO_USD:.0f} dólares.")
    return round(float(valor), 2)


def color_sobre(color: str) -> str:
    """El color del texto que se lee bien encima de `color`: blanco sobre oscuro, casi negro sobre claro."""
    rojo, verde, azul = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def lineal(canal: float) -> float:
        return canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4

    luminancia = 0.2126 * lineal(rojo) + 0.7152 * lineal(verde) + 0.0722 * lineal(azul)
    return "#FFFFFF" if luminancia < 0.36 else "#111827"


def guardar_logo(origen: Path, destino: Path) -> None:
    """Comprueba el logo como una foto (tipo por contenido, peso y píxeles) y lo guarda como PNG pequeño.

    Nunca se guarda el archivo tal como llegó: se vuelve a crear con Pillow. Un SVG no se acepta.
    """
    origen = Path(origen)
    peso = origen.stat().st_size
    if peso > LOGO_MAX_MB * 1024 * 1024:
        megas = math.ceil(peso / (1024 * 1024) * 10) / 10
        raise ErrorAjustes(f"El logo pesa {numero(megas)} MB: el máximo es {LOGO_MAX_MB}.")
    with origen.open("rb") as archivo:
        tipo = detectar_tipo(archivo.read(32))
    if tipo not in ("jpeg", "png", "webp"):
        raise ErrorAjustes(MENSAJE_LOGO_FORMATO)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(origen, formats=[tipo.upper()]) as imagen:
                if imagen.width * imagen.height > MAX_MEGAPIXELES * 1_000_000:
                    raise ErrorAjustes("El logo es demasiado grande: redúcelo y vuelve a subirlo.")
                imagen.load()
                logo = imagen.convert("RGBA")
    except ErrorAjustes:
        raise
    except Exception:
        raise ErrorAjustes(MENSAJE_LOGO_DANADO)
    logo.thumbnail((LOGO_LADO, LOGO_LADO), Image.Resampling.LANCZOS)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(f"{destino.name}.tmp-{os.getpid()}")
    logo.save(temporal, "PNG")
    os.replace(temporal, destino)
