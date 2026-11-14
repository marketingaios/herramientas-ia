"""Preparación común de las pruebas.

Las pruebas trabajan siempre en una carpeta temporal (dentro de `estudio-fotos/.pruebas-tmp/`) y con un simulador de
OpenRouter: nunca leen ni escriben el `.env` real, `ajustes.json`, `salidas/` ni `gastos.jsonl`, y nunca llaman a
OpenRouter de verdad.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest

CARPETA = Path(__file__).resolve().parent.parent  # estudio-fotos
RAIZ = CARPETA.parent  # herramientas-ia
MUESTRAS = RAIZ / "muestras"
EXTENSIONES_DE_FOTO = {".jpg", ".jpeg", ".png", ".webp"}

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


def fotos_de_muestra() -> list[Path]:
    """Todas las fotos de `muestras/`, ordenadas por nombre: las pruebas usan las que haya, sin un número fijo."""
    fotos = sorted(ruta for ruta in MUESTRAS.iterdir() if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_DE_FOTO)
    assert len(fotos) >= 3, "en muestras/ hacen falta al menos 3 fotos para los recorridos de las pruebas"
    assert len(fotos) <= 20, "en muestras/ hay más de 20 fotos: no caben en una sola subida"
    return fotos


def lado_corto(foto: Path) -> int:
    """El lado corto de una foto de muestra, en píxeles (por debajo de 1.000, la herramienta la acepta con un aviso)."""
    from PIL import Image

    with Image.open(foto) as imagen:
        return min(imagen.size)


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


@pytest.fixture(scope="session", autouse=True)
def sin_internet():
    """Vigilante: desde las pruebas no sale ninguna petición a internet. Solo se habla con este computador."""
    original = httpx.HTTPTransport.handle_request

    def solo_local(self, peticion):
        if peticion.url.host not in ("127.0.0.1", "localhost"):
            raise AssertionError("Una prueba intentó llamar a internet: las pruebas solo usan el simulador local.")
        return original(self, peticion)

    httpx.HTTPTransport.handle_request = solo_local
    yield
    httpx.HTTPTransport.handle_request = original


@pytest.fixture(autouse=True)
def carpeta_temporal_del_sistema():
    """El servidor manda sus temporales a `trabajo/` (y el acelerador, los suyos): después de cada prueba se deja
    todo como estaba."""
    antes, variable = tempfile.tempdir, os.environ.get("TMPDIR")
    yield
    tempfile.tempdir = antes
    if variable is None:
        os.environ.pop("TMPDIR", None)
    else:
        os.environ["TMPDIR"] = variable


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


@pytest.fixture(scope="session")
def _simulador_en_marcha():
    from simulador import Simulador

    simulador = Simulador().arrancar()
    yield simulador
    simulador.parar()


@pytest.fixture
def simulador(_simulador_en_marcha, clave_falsa):
    """El OpenRouter de mentira, recién reiniciado y aceptando la clave falsa de esta ejecución."""
    _simulador_en_marcha.reiniciar()
    _simulador_en_marcha.clave = clave_falsa
    return _simulador_en_marcha


@pytest.fixture
def config_simulador(carpeta_datos: Path, simulador):
    """Como `config`, pero con OpenRouter apuntando al simulador."""
    from estudio.config import para_pruebas

    configuracion = para_pruebas(carpeta_datos, openrouter_url=simulador.url)
    configuracion.preparar_carpetas()
    return configuracion


class ServidorDePruebas:
    """El servidor de la herramienta, arrancado de verdad en 127.0.0.1 (en un puerto libre) para una prueba."""

    def __init__(self, config, estudio=None):
        import uvicorn

        from estudio.estudio import Estudio
        from estudio.servidor import crear_aplicacion

        self.config = config
        self.estudio = estudio or Estudio(config)
        self.app = crear_aplicacion(config, self.estudio)
        self._uvicorn = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning", access_log=False)
        )
        self._hilo = threading.Thread(target=self._uvicorn.run, name="servidor-de-pruebas", daemon=True)
        self._hilo.start()
        limite = time.monotonic() + 15
        while not self._uvicorn.started:
            assert time.monotonic() < limite, "el servidor de pruebas no arrancó"
            time.sleep(0.01)
        self.puerto = self._uvicorn.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{self.puerto}"
        self.cliente = httpx.Client(base_url=self.url, trust_env=False, timeout=60)

    def esperar(self, tipo: str, segundos: float = 60) -> None:
        assert self.estudio.esperar(tipo, segundos), f"el trabajo «{tipo}» no terminó a tiempo"

    def parar(self) -> None:
        self.cliente.close()
        self._uvicorn.should_exit = True
        self._hilo.join(timeout=10)
        self.estudio.cerrar()


@pytest.fixture
def servidor(config_simulador):
    """El servidor con los datos en la carpeta temporal, el recorte simulado y OpenRouter simulado."""
    servidor = ServidorDePruebas(config_simulador)
    yield servidor
    servidor.parar()
