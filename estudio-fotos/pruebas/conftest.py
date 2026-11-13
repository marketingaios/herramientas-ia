"""Preparación común de las pruebas.

Las pruebas trabajan siempre en una carpeta temporal (dentro de `estudio-fotos/.pruebas-tmp/`) y con un simulador de
OpenRouter: nunca leen ni escriben el `.env` real, `ajustes.json`, `salidas/` ni `gastos.jsonl`, y nunca llaman a
OpenRouter de verdad.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest

CARPETA = Path(__file__).resolve().parent.parent  # estudio-fotos
RAIZ = CARPETA.parent  # herramientas-ia
MUESTRAS = RAIZ / "muestras"

# Un puerto local donde no escucha nadie: si una prueba rápida intentara hablar con «OpenRouter», fallaría la conexión.
SIN_SERVIDOR = "http://127.0.0.1:9/api/v1"

_VARIABLES = ("ESTUDIO_CARPETA_DATOS", "ESTUDIO_OPENROUTER_URL", "ESTUDIO_RECORTADOR", "ESTUDIO_PUERTO")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = str(CARPETA / ".pruebas-tmp")
    # Chromium de Playwright, dentro de la carpeta y no en la carpeta personal.
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(CARPETA / ".navegadores"))
    for variable in _VARIABLES:
        os.environ.pop(variable, None)


def _huella_de_los_archivos_reales() -> dict:
    """Tamaño y fecha de los archivos reales del usuario, sin abrir ninguno."""
    huella: dict = {}
    for ruta in (
        RAIZ / ".env",
        CARPETA / "ajustes.json",
        CARPETA / "gastos.jsonl",
        CARPETA / "logo_negocio.png",
    ):
        try:
            datos = ruta.stat()
            huella[ruta.name] = (datos.st_size, datos.st_mtime_ns)
        except FileNotFoundError:
            huella[ruta.name] = None
    salidas = CARPETA / "salidas"
    huella["salidas"] = (
        sorted((p.relative_to(salidas).as_posix(), p.stat().st_mtime_ns) for p in salidas.rglob("*"))
        if salidas.exists()
        else None
    )
    return huella


@pytest.fixture(scope="session", autouse=True)
def archivos_reales_intactos():
    """Vigilante: ninguna prueba puede tocar el .env real, ajustes.json, gastos.jsonl ni salidas/."""
    antes = _huella_de_los_archivos_reales()
    yield
    despues = _huella_de_los_archivos_reales()
    cambiados = [nombre for nombre in antes if antes[nombre] != despues[nombre]]
    assert not cambiados, f"Las pruebas tocaron archivos reales del usuario: {cambiados}"


@pytest.fixture(scope="session")
def clave_falsa() -> str:
    """Una clave con la forma de las de OpenRouter, inventada en cada ejecución (nunca escrita en el código)."""
    return "sk-or-v1-" + secrets.token_hex(32)


@pytest.fixture
def carpeta_datos(tmp_path: Path) -> Path:
    carpeta = tmp_path / "datos"
    carpeta.mkdir()
    return carpeta


@pytest.fixture
def config(carpeta_datos: Path):
    """Configuración de pruebas: datos en la carpeta temporal, recorte simulado y sin OpenRouter."""
    from estudio.config import para_pruebas

    configuracion = para_pruebas(carpeta_datos, openrouter_url=SIN_SERVIDOR)
    configuracion.preparar_carpetas()
    return configuracion
