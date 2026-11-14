"""Los ajustes de la herramienta, sin la clave: `estudio-fotos/ajustes.json`.

Son tres: la calidad del recorte, el modelo de las escenas y el tope de gasto por sesión.
La clave de OpenRouter NO está aquí: vive solo en `.env` (ver `clave.py`).
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path

from . import costos, equipo

POR_DEFECTO = {
    "calidad_recorte": "automatica",
    "modelo_escenas": costos.MODELO_POR_DEFECTO,
    "tope_sesion_usd": costos.TOPE_POR_DEFECTO_USD,
}
CAMPOS = tuple(POR_DEFECTO)  # lo único que se lee, se cambia y se guarda


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
    for campo in CAMPOS:
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
    """Los ajustes con los cambios pedidos, ya comprobados. Lo que no viene en `cambios` no se toca.

    Cualquier otro campo que llegue se ignora: ni se comprueba ni se guarda.
    """
    if not isinstance(cambios, dict):
        raise ErrorAjustes("Los ajustes no tienen la forma esperada.")
    nuevos = {campo: copy.deepcopy(actuales[campo]) for campo in CAMPOS}

    if "calidad_recorte" in cambios:
        if not isinstance(cambios["calidad_recorte"], str) or cambios["calidad_recorte"] not in equipo.CALIDADES:
            raise ErrorAjustes("La calidad del recorte debe ser Automática, Máxima o Rápida.")
        nuevos["calidad_recorte"] = cambios["calidad_recorte"]

    if "modelo_escenas" in cambios:
        if not isinstance(cambios["modelo_escenas"], str) or cambios["modelo_escenas"] not in costos.IDS_MODELOS:
            raise ErrorAjustes("Ese modelo de escenas no está en la lista.")
        nuevos["modelo_escenas"] = cambios["modelo_escenas"]

    if "tope_sesion_usd" in cambios:
        nuevos["tope_sesion_usd"] = _tope(cambios["tope_sesion_usd"])
    return nuevos


def _tope(valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ErrorAjustes("El tope de gasto debe ser un número, por ejemplo 1.")
    if not 0 <= valor <= costos.TOPE_MAXIMO_USD:
        raise ErrorAjustes(f"El tope de gasto debe estar entre 0 y {costos.TOPE_MAXIMO_USD:.0f} dólares.")
    return round(float(valor), 2)
