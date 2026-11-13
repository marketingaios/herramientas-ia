"""Registros sin claves ni rutas personales.

Todo lo que la herramienta escribe en la consola pasa por aquí: se tapa cualquier cosa con forma de clave de
OpenRouter y la carpeta personal se cambia por «~».
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_CLAVE = re.compile(r"sk-or-[A-Za-z0-9_\-]{6,}")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}")
TAPADO = "••••"


def limpiar(texto: str) -> str:
    """Un texto sin claves ni la ruta de la carpeta personal."""
    texto = _CLAVE.sub(TAPADO, str(texto))
    texto = _BEARER.sub(r"\1" + TAPADO, texto)
    personal = str(Path.home())
    if personal and personal != "/":
        texto = texto.replace(personal, "~")
    return texto


class _Filtro(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        registro.msg = limpiar(registro.getMessage())
        registro.args = ()
        if registro.exc_info:  # las trazas llevan rutas del computador: basta con el tipo y el mensaje
            tipo, error = registro.exc_info[0], registro.exc_info[1]
            registro.msg += f" ({getattr(tipo, '__name__', 'error')}: {limpiar(error)})"
            registro.exc_info = None
            registro.exc_text = None
        return True


def preparar() -> logging.Logger:
    """El registro de la herramienta, con el filtro puesto también en los de uvicorn."""
    filtro = _Filtro()
    registro = logging.getLogger("estudio")
    if not registro.handlers:
        salida = logging.StreamHandler()
        salida.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        registro.addHandler(salida)
        registro.setLevel(logging.INFO)
        registro.propagate = False
    for nombre in ("estudio", "uvicorn", "uvicorn.error", "uvicorn.access"):
        otro = logging.getLogger(nombre)
        if not any(isinstance(f, _Filtro) for f in otro.filters):
            otro.addFilter(filtro)
        for manejador in otro.handlers:
            if not any(isinstance(f, _Filtro) for f in manejador.filters):
                manejador.addFilter(filtro)
    return registro


registro = logging.getLogger("estudio")
