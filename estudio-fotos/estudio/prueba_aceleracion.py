"""Prueba un acelerador con el modelo de recorte, en un proceso aparte.

Lo lanza `equipo.Aceleracion`, así:

    python -m estudio.prueba_aceleracion <modelo> <carpeta de modelos> <resultado.json> [<segundos como máximo>]

Prepara el modelo con CoreML, recorta una foto de prueba (dibujada aquí mismo: no usa ninguna foto del usuario) y
escribe cuánto tardó. Si CoreML se cuelga o tarda minutos, quien lo lanzó corta este proceso; por si quien lo lanzó
desaparece, el proceso también se pone su propio límite. No descarga nada: el modelo tiene que estar ya en la carpeta.
"""

from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

from . import equipo
from .recorte import comprobar_modelo, crear_sesion, ruta_modelo


def foto_de_prueba() -> Image.Image:
    """Un «producto» sencillo sobre un fondo liso, de 1024×1024 (el tamaño con el que trabaja el modelo)."""
    foto = Image.new("RGB", (1024, 1024), (214, 208, 196))
    ImageDraw.Draw(foto).rounded_rectangle((352, 224, 672, 800), radius=36, fill=(122, 78, 44))
    return foto


def probar(modelo: str, carpeta_modelos: Path) -> dict:
    inicio = time.perf_counter()
    sesion = crear_sesion(modelo, carpeta_modelos, equipo.PROVEEDORES_COREML)
    if "CoreMLExecutionProvider" not in sesion.inner_session.get_providers():
        return {"estado": "sin_acelerador"}
    foto = foto_de_prueba()
    sesion.predict(foto)  # la primera pasada termina de preparar el modelo
    preparar = time.perf_counter() - inicio
    inicio = time.perf_counter()
    sesion.predict(foto)
    return {"estado": "bien", "preparar_s": round(preparar, 1), "segundos": round(time.perf_counter() - inicio, 2)}


def main(argumentos: list[str]) -> int:
    if len(argumentos) not in (3, 4):
        return 2
    try:
        modelo = comprobar_modelo(argumentos[0])
        limite = float(argumentos[3]) if len(argumentos) == 4 else float(equipo.TIEMPO_MAXIMO)
        alarma = int(min(max(1.0, limite), 600.0)) + 10
    except (ValueError, OverflowError):
        return 2
    carpeta_modelos, salida = Path(argumentos[1]), Path(argumentos[2])
    if not ruta_modelo(carpeta_modelos, modelo).is_file():
        return 2  # desde aquí no se descarga nada
    if hasattr(signal, "alarm"):
        signal.alarm(alarma)  # pasado el tiempo máximo, el sistema corta este proceso
    resultado = probar(modelo, carpeta_modelos)
    salida.write_text(json.dumps(resultado), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
