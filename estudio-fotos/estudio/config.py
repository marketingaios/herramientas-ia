"""Rutas y variables de entorno del estudio de fotos.

Todo lo que la herramienta escribe queda dentro de `herramientas-ia`. Las variables `ESTUDIO_*` existen solo para las
pruebas automáticas: mandan los datos a una carpeta temporal y cambian OpenRouter por un simulador local.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PUERTO = 8601
OPENROUTER_URL = "https://openrouter.ai/api/v1"

CARPETA = Path(__file__).resolve().parent.parent  # herramientas-ia/estudio-fotos
RAIZ = CARPETA.parent  # herramientas-ia

_LOCALES = {"127.0.0.1", "localhost"}


@dataclass(frozen=True)
class Config:
    """Dónde está cada cosa. `datos_raiz` y `datos` solo cambian en las pruebas."""

    raiz: Path = RAIZ
    carpeta: Path = CARPETA
    datos_raiz: Path = RAIZ
    datos: Path = CARPETA
    openrouter_url: str = OPENROUTER_URL
    recortador: str = "rembg"  # «rembg» (el de verdad) o «simulado» (pruebas)

    # Archivos comunes de herramientas-ia
    @property
    def env(self) -> Path:
        return self.datos_raiz / ".env"

    @property
    def modelos(self) -> Path:
        return self.raiz / "modelos"

    @property
    def estilo(self) -> Path:
        return self.raiz / "estilo"

    @property
    def marca(self) -> Path:
        return self.raiz / "marca"

    # Archivos de esta herramienta
    @property
    def web(self) -> Path:
        return self.carpeta / "web"

    @property
    def plataformas(self) -> Path:
        return self.carpeta / "plataformas.json"

    @property
    def ajustes(self) -> Path:
        return self.datos / "ajustes.json"

    @property
    def logo(self) -> Path:
        return self.datos / "logo_negocio.png"

    @property
    def gastos(self) -> Path:
        return self.datos / "gastos.jsonl"

    @property
    def medicion(self) -> Path:
        return self.datos / "medicion.json"

    @property
    def trabajo(self) -> Path:
        return self.datos / "trabajo"

    @property
    def salidas(self) -> Path:
        return self.datos / "salidas"

    def preparar_carpetas(self) -> None:
        for carpeta in (self.modelos, self.trabajo, self.salidas):
            carpeta.mkdir(parents=True, exist_ok=True)


def para_pruebas(carpeta_temporal: Path, *, openrouter_url: str = OPENROUTER_URL, recortador: str = "simulado") -> Config:
    """Una configuración cuyos datos (.env, ajustes, gastos, trabajo y salidas) van a una carpeta temporal."""
    carpeta_temporal = Path(carpeta_temporal)
    return Config(
        datos_raiz=carpeta_temporal,
        datos=carpeta_temporal / "estudio-fotos",
        openrouter_url=_url_openrouter(openrouter_url),
        recortador=recortador,
    )


def desde_entorno() -> Config:
    """La configuración normal, o la de pruebas si están las variables `ESTUDIO_*`."""
    url_pruebas = os.environ.get("ESTUDIO_OPENROUTER_URL", "").strip()
    carpeta_datos = os.environ.get("ESTUDIO_CARPETA_DATOS", "").strip()
    simulado = os.environ.get("ESTUDIO_RECORTADOR", "").strip() == "simulado"

    if not url_pruebas and not carpeta_datos and not simulado:
        return Config()

    # Salvaguarda: el modo de pruebas va entero o no arranca. Con el simulador pero sin carpeta temporal se
    # escribiría el .env real; con la carpeta temporal pero sin simulador se llamaría a OpenRouter de verdad.
    if not (url_pruebas and carpeta_datos):
        raise ValueError(
            "Las variables de pruebas van juntas: ESTUDIO_CARPETA_DATOS (una carpeta temporal) y "
            "ESTUDIO_OPENROUTER_URL (el simulador). Para usar la herramienta, quita las variables ESTUDIO_*."
        )
    url = _url_openrouter(url_pruebas)
    if url == OPENROUTER_URL:
        raise ValueError("ESTUDIO_OPENROUTER_URL solo sirve para las pruebas y debe apuntar al simulador local.")
    carpeta = Path(carpeta_datos).resolve()
    if carpeta in (RAIZ, CARPETA):
        raise ValueError("ESTUDIO_CARPETA_DATOS debe ser una carpeta temporal, no la carpeta de la herramienta.")
    return para_pruebas(carpeta, openrouter_url=url, recortador="simulado" if simulado else "rembg")


def _url_openrouter(url: str) -> str:
    """Solo se admite OpenRouter o, para las pruebas, un simulador en este mismo computador.

    Así ninguna variable de entorno puede mandar la clave a otro servidor.
    """
    url = url.rstrip("/")
    if url == OPENROUTER_URL:
        return url
    partes = urlparse(url)
    if partes.scheme == "http" and partes.hostname in _LOCALES:
        return url
    raise ValueError(
        "ESTUDIO_OPENROUTER_URL solo sirve para las pruebas y debe apuntar a 127.0.0.1 o localhost."
    )


def puerto_inicial() -> int:
    """El puerto de partida: 8601, salvo en las pruebas (`ESTUDIO_PUERTO`)."""
    valor = os.environ.get("ESTUDIO_PUERTO", "").strip()
    if valor.isdigit() and 1024 <= int(valor) <= 65000:
        return int(valor)
    return PUERTO
