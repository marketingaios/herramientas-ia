"""Registros sin claves ni rutas personales.

Todo lo que la herramienta escribe en la consola pasa por aquí: se tapa cualquier cosa con forma de clave de
OpenRouter y la carpeta personal se cambia por «~». También lo que escriben las librerías: sus registros, los avisos
de Python y los errores no controlados (de esos se escribe solo el tipo y dónde saltaron, nunca la traza).
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from pathlib import Path

_CLAVE = re.compile(r"sk-or-[A-Za-z0-9_\-]{6,}")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}")
TAPADO = "••••"
_FORMATO = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

MENSAJE_ERROR = "Error inesperado (%s%s). Vuelve a abrir la herramienta; si se repite, enseña este mensaje a quien la mantiene."
MENSAJE_ERROR_DE_FONDO = (
    "Error inesperado en segundo plano (%s%s). Si algo deja de avanzar, cierra la herramienta y vuelve a abrirla."
)


def _carpeta_personal() -> list[str]:
    """La carpeta personal, escrita de las formas en que puede aparecer (en Windows, también con «/»)."""
    try:
        personal = Path.home()
    except (RuntimeError, OSError):
        return []
    formas = {str(personal), personal.as_posix()}
    return sorted((forma for forma in formas if len(forma) > 1), key=len, reverse=True)


def limpiar(texto: str) -> str:
    """Un texto sin claves ni la ruta de la carpeta personal."""
    texto = _CLAVE.sub(TAPADO, str(texto))
    texto = _BEARER.sub(r"\1" + TAPADO, texto)
    for personal in _carpeta_personal():
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
        registro.stack_info = None
        return True


_FILTRO = _Filtro()


def _poner_filtro(otro: logging.Logger) -> None:
    """El filtro, en un registro y en cada una de sus salidas."""
    if not any(isinstance(f, _Filtro) for f in otro.filters):
        otro.addFilter(_FILTRO)
    for manejador in otro.handlers:
        if not any(isinstance(f, _Filtro) for f in manejador.filters):
            manejador.addFilter(_FILTRO)


def preparar() -> logging.Logger:
    """El registro de la herramienta, con el filtro puesto también en los de uvicorn."""
    registro = logging.getLogger("estudio")
    if not registro.handlers:
        salida = logging.StreamHandler()
        salida.setFormatter(_FORMATO)
        registro.addHandler(salida)
        registro.setLevel(logging.INFO)
        registro.propagate = False
    for nombre in ("estudio", "uvicorn", "uvicorn.error", "uvicorn.access"):
        _poner_filtro(logging.getLogger(nombre))
    return registro


def proteger_descargas() -> None:
    """El filtro, también en el registro de pooch.

    rembg descarga el modelo con pooch, que tiene un registro propio (no sale de `logging.getLogger`) y escribe en la
    consola la ruta completa del archivo que descarga: «Downloading data from … to file …».
    """
    try:
        import pooch

        _poner_filtro(pooch.get_logger())
    except Exception:  # sin pooch no hay descarga ni nada que filtrar
        pass


def _donde(traza) -> str:
    """El archivo (sin su carpeta) y la línea donde saltó el error."""
    while traza is not None and traza.tb_next is not None:
        traza = traza.tb_next
    if traza is None:
        return ""
    return f", en {Path(traza.tb_frame.f_code.co_filename).name}:{traza.tb_lineno}"


def _error_no_controlado(tipo, error, traza) -> None:
    """En vez de la traza de Python, que lleva las rutas del computador: el tipo del error y dónde saltó."""
    if issubclass(tipo, KeyboardInterrupt):
        return
    registro.error(MENSAJE_ERROR, tipo.__name__, _donde(traza))


def _error_en_un_hilo(datos) -> None:
    if datos.exc_type is None or issubclass(datos.exc_type, SystemExit):
        return
    registro.error(MENSAJE_ERROR_DE_FONDO, datos.exc_type.__name__, _donde(datos.exc_traceback))


def proteger_consola() -> logging.Logger:
    """Todo lo demás que puede llegar a la consola pasa también por el filtro. Se llama una vez, al arrancar.

    - Los registros de las librerías (asyncio, PIL…) suben al registro raíz: se le pone una salida con el filtro.
    - Los avisos de Python (`warnings`) llevan la ruta del archivo que avisa: van a ese mismo registro.
    - Los errores no controlados, en el hilo principal o en otro: sin la traza.
    """
    propio = preparar()
    raiz = logging.getLogger()
    if not raiz.handlers:
        salida = logging.StreamHandler()
        salida.setFormatter(_FORMATO)
        raiz.addHandler(salida)
    _poner_filtro(raiz)
    if logging.lastResort is not None and not any(isinstance(f, _Filtro) for f in logging.lastResort.filters):
        logging.lastResort.addFilter(_FILTRO)  # la salida de los registros sueltos, sin salida propia
    logging.captureWarnings(True)
    proteger_descargas()
    sys.excepthook = _error_no_controlado
    threading.excepthook = _error_en_un_hilo
    return propio


registro = logging.getLogger("estudio")
