"""Paso 2: la configuración y la salvaguarda del modo de pruebas."""

from __future__ import annotations

import pytest

from conftest import CARPETA, RAIZ
from estudio import config as cfg

SIMULADOR = "http://127.0.0.1:8999/api/v1"


@pytest.fixture
def entorno(monkeypatch):
    for variable in ("ESTUDIO_CARPETA_DATOS", "ESTUDIO_OPENROUTER_URL", "ESTUDIO_RECORTADOR", "ESTUDIO_PUERTO"):
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def test_la_configuracion_normal_no_sale_de_herramientas_ia(entorno):
    configuracion = cfg.desde_entorno()
    assert configuracion.openrouter_url == "https://openrouter.ai/api/v1"
    assert configuracion.recortador == "rembg"
    assert configuracion.env == RAIZ / ".env"
    assert configuracion.modelos == RAIZ / "modelos"
    for ruta in (configuracion.ajustes, configuracion.gastos, configuracion.trabajo, configuracion.salidas,
                 configuracion.logo_antiguo, configuracion.medicion):
        assert ruta.parent == CARPETA
    assert configuracion.logo_antiguo.name == "logo_negocio.png"  # el que dejó la versión 1: solo para borrarlo


def test_en_pruebas_todos_los_datos_van_a_la_carpeta_temporal(entorno, tmp_path):
    entorno.setenv("ESTUDIO_CARPETA_DATOS", str(tmp_path))
    entorno.setenv("ESTUDIO_OPENROUTER_URL", SIMULADOR)
    entorno.setenv("ESTUDIO_RECORTADOR", "simulado")
    configuracion = cfg.desde_entorno()
    assert configuracion.openrouter_url == SIMULADOR
    assert configuracion.recortador == "simulado"
    temporal = tmp_path.resolve()
    for ruta in (configuracion.env, configuracion.ajustes, configuracion.gastos, configuracion.trabajo,
                 configuracion.salidas, configuracion.logo_antiguo, configuracion.medicion):
        assert temporal in ruta.parents, f"{ruta.name} quedaría fuera de la carpeta temporal"
    # Lo que no es del usuario se sigue leyendo de la carpeta de la herramienta.
    assert configuracion.plataformas == CARPETA / "plataformas.json"
    assert configuracion.modelos == RAIZ / "modelos"


@pytest.mark.parametrize(
    "variables",
    [
        {"ESTUDIO_OPENROUTER_URL": SIMULADOR},  # simulador sin carpeta temporal: escribiría el .env real
        {"ESTUDIO_CARPETA_DATOS": "TEMPORAL"},  # carpeta temporal sin simulador: llamaría a OpenRouter de verdad
        {"ESTUDIO_RECORTADOR": "simulado"},
        {"ESTUDIO_CARPETA_DATOS": "TEMPORAL", "ESTUDIO_OPENROUTER_URL": "https://openrouter.ai/api/v1"},
    ],
)
def test_el_modo_de_pruebas_va_entero_o_no_arranca(entorno, tmp_path, variables):
    for nombre, valor in variables.items():
        entorno.setenv(nombre, str(tmp_path) if valor == "TEMPORAL" else valor)
    with pytest.raises(ValueError):
        cfg.desde_entorno()


@pytest.mark.parametrize("carpeta", [RAIZ, CARPETA])
def test_la_carpeta_de_pruebas_no_puede_ser_la_de_la_herramienta(entorno, carpeta):
    entorno.setenv("ESTUDIO_CARPETA_DATOS", str(carpeta))
    entorno.setenv("ESTUDIO_OPENROUTER_URL", SIMULADOR)
    with pytest.raises(ValueError):
        cfg.desde_entorno()


@pytest.mark.parametrize(
    "url",
    ["https://example.com/api/v1", "http://192.168.1.20:8000/api/v1", "http://openrouter.ai.example.com/api/v1",
     "https://127.0.0.1.example.com/api/v1"],
)
def test_el_simulador_solo_puede_estar_en_este_computador(entorno, tmp_path, url):
    entorno.setenv("ESTUDIO_CARPETA_DATOS", str(tmp_path))
    entorno.setenv("ESTUDIO_OPENROUTER_URL", url)
    with pytest.raises(ValueError):
        cfg.desde_entorno()


def test_el_puerto_de_partida_es_el_8601(entorno):
    assert cfg.puerto_inicial() == 8601
    entorno.setenv("ESTUDIO_PUERTO", "8750")
    assert cfg.puerto_inicial() == 8750
    entorno.setenv("ESTUDIO_PUERTO", "80")
    assert cfg.puerto_inicial() == 8601
