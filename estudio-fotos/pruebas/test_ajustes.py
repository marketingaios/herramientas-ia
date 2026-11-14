"""Paso 8 (y paso 26, versión 1.1): los ajustes en el `ajustes.json` de la carpeta temporal.

Son tres: la calidad del recorte, el modelo de las escenas y el tope de gasto. Desde la versión 1.1 no hay marca del
negocio: ni nombre, ni colores, ni logo.
"""

from __future__ import annotations

import json

import pytest

from conftest import CARPETA
from estudio import ajustes as los_ajustes
from estudio import costos
from estudio.estudio import ErrorEstudio, Estudio

LOS_TRES = {"calidad_recorte", "modelo_escenas", "tope_sesion_usd"}
# Lo que enviaba la página de la versión 1 (o cualquiera que lo imite): ya no significa nada.
MARCA_ANTIGUA = {"nombre": "Mi tienda", "color_principal": "#123456", "color_acento": "#ABCDEF"}


@pytest.fixture
def estudio(config):
    estudio = Estudio(config)
    yield estudio
    estudio.cerrar()


# --- Valores de fábrica y tabla de modelos --------------------------------------------------------------------------


def test_los_modelos_de_escenas_son_los_de_la_ficha():
    assert [(m["id"], m["nombre"], m["costo_partida_usd"]) for m in costos.MODELOS_ESCENAS] == [
        ("google/gemini-nano-banana-2.1", "Nano Banana 2.1", 0.04),
        ("google/gemini-3.1-flash-lite-image", "Nano Banana 2 Lite", 0.04),
        ("google/gemini-3.1-flash-image", "Nano Banana 2", 0.07),
        ("google/gemini-3-pro-image", "Nano Banana Pro", 0.14),
    ]
    assert [m["id"] for m in costos.MODELOS_ESCENAS if m["recomendado"]] == ["google/gemini-nano-banana-2.1"]
    assert costos.modelos_publicos()[0] == {
        "id": "google/gemini-nano-banana-2.1", "nombre": "Nano Banana 2.1 (recomendado)", "costo_partida": "0,04 $",
    }
    assert costos.modelos_publicos()[3]["costo_partida"] == "0,14 $"


def test_de_fabrica_calidad_automatica_modelo_recomendado_y_tope_de_un_dolar(estudio, config):
    assert not config.ajustes.exists()
    assert set(los_ajustes.POR_DEFECTO) == LOS_TRES and set(los_ajustes.CAMPOS) == LOS_TRES
    estado = estudio.publico()
    assert estado["ajustes"] == {
        "calidad_recorte": "automatica",
        "modelo_escenas": "google/gemini-nano-banana-2.1",
        "tope_sesion_usd": 1.0,
        "tope_texto": "1,00 $",
    }
    assert "negocio" not in estado and set(estudio.ajustes) == LOS_TRES


# --- Guardar ----------------------------------------------------------------------------------------------------------


def test_los_ajustes_se_guardan_en_ajustes_json_y_se_recuperan(estudio, config):
    estudio.cambiar_ajustes({"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5})
    guardado = json.loads(config.ajustes.read_text(encoding="utf-8"))
    assert guardado == {"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5}
    assert "clave" not in config.ajustes.read_text(encoding="utf-8").lower()

    otro = Estudio(config)  # como si se reiniciara la herramienta
    assert otro.publico()["ajustes"]["tope_texto"] == "2,50 $"
    assert otro.publico()["ajustes"]["modelo_escenas"] == "google/gemini-3-pro-image"
    assert otro.publico()["modelo"]["etiqueta"] == "Modo rápido"


def test_se_puede_cambiar_un_solo_ajuste(estudio):
    estudio.cambiar_ajustes({"tope_sesion_usd": 3})
    estudio.cambiar_ajustes({"modelo_escenas": "google/gemini-3.1-flash-image"})
    ajustes = estudio.publico()["ajustes"]
    assert (ajustes["tope_sesion_usd"], ajustes["modelo_escenas"]) == (3.0, "google/gemini-3.1-flash-image")
    assert ajustes["calidad_recorte"] == "automatica"


@pytest.mark.parametrize("marca", [MARCA_ANTIGUA, {"color_principal": "rojo"}, {"nombre": "x" * 5000}, "un texto", ["lista"], 7, None])
def test_la_marca_del_negocio_ya_no_existe_lo_que_llegue_se_ignora_y_no_se_guarda(estudio, config, marca):
    """La página ya no la envía. Si llega (una página antigua abierta, o cualquiera), ni se comprueba ni se guarda."""
    estudio.cambiar_ajustes({"negocio": marca, "logo": "logo.png", "otra_cosa": {"a": 1}, "tope_sesion_usd": 2})
    guardado = json.loads(config.ajustes.read_text(encoding="utf-8"))
    assert guardado == {"calidad_recorte": "automatica", "modelo_escenas": "google/gemini-nano-banana-2.1", "tope_sesion_usd": 2.0}
    estado = estudio.publico()
    assert "negocio" not in estado and set(estudio.ajustes) == LOS_TRES
    for texto in (config.ajustes.read_text(encoding="utf-8"), json.dumps(estado, ensure_ascii=False)):
        assert "Mi tienda" not in texto and "#123456" not in texto and "color_principal" not in texto


def test_el_estudio_ya_no_guarda_ni_sirve_ningun_logo(estudio, config):
    for nombre in ("guardar_logo", "quitar_logo", "_negocio_publico"):
        assert not hasattr(estudio, nombre), nombre
    for nombre in ("guardar_logo", "color_sobre", "LOGO_MAX_MB", "NOMBRE_MAXIMO"):
        assert not hasattr(los_ajustes, nombre), nombre
    assert not hasattr(config, "logo")
    for archivo in ("ajustes.py", "estudio.py", "servidor.py"):
        codigo = (CARPETA / "estudio" / archivo).read_text(encoding="utf-8")
        for resto in ('"negocio"', "color_principal", "color_acento", "/api/logo", "ajustes/logo", "guardar_logo"):
            assert resto not in codigo, f"{archivo}: {resto}"


def test_la_calidad_del_recorte_cambia_el_modelo(estudio):
    estudio.cambiar_ajustes({"calidad_recorte": "maxima"})
    assert estudio.publico()["modelo"]["nombre"] == "birefnet-general"
    estudio.cambiar_ajustes({"calidad_recorte": "rapida"})
    assert (estudio.publico()["modelo"]["nombre"], estudio.publico()["modelo"]["total_mb"]) == ("birefnet-general-lite", 224)


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"calidad_recorte": "turbo"}, "La calidad del recorte debe ser Automática, Máxima o Rápida."),
        ({"calidad_recorte": ["maxima"]}, "La calidad del recorte debe ser Automática, Máxima o Rápida."),
        ({"modelo_escenas": "openai/otro-modelo"}, "Ese modelo de escenas no está en la lista."),
        ({"modelo_escenas": ""}, "Ese modelo de escenas no está en la lista."),
        ({"tope_sesion_usd": -1}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": 5000}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": "mucho"}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": float("nan")}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": True}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"negocio": MARCA_ANTIGUA, "tope_sesion_usd": -1}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ("no es un objeto", "Los ajustes no tienen la forma esperada."),
    ],
)
def test_un_ajuste_que_no_vale_se_rechaza_y_no_se_guarda_nada(estudio, config, cambios, mensaje):
    antes = estudio.publico()
    with pytest.raises(ErrorEstudio) as error:
        estudio.cambiar_ajustes(cambios)
    assert str(error.value) == mensaje
    assert not config.ajustes.exists()
    assert estudio.publico()["ajustes"] == antes["ajustes"]


def test_un_ajustes_json_roto_no_impide_arrancar(config):
    config.ajustes.parent.mkdir(parents=True, exist_ok=True)
    config.ajustes.write_text("{ roto", encoding="utf-8")
    assert Estudio(config).publico()["ajustes"]["tope_sesion_usd"] == 1.0

    config.ajustes.write_text(json.dumps({
        "modelo_escenas": "modelo/desconocido", "tope_sesion_usd": 4, "calidad_recorte": "maxima",
    }), encoding="utf-8")
    estado = Estudio(config).publico()
    assert estado["ajustes"]["tope_sesion_usd"] == 4.0 and estado["ajustes"]["calidad_recorte"] == "maxima"
    assert estado["ajustes"]["modelo_escenas"] == "google/gemini-nano-banana-2.1"  # el desconocido vuelve al de fábrica


def test_un_ajustes_json_de_la_version_1_se_lee_sin_su_marca(config):
    """El archivo que dejó la versión 1 trae la marca del negocio: los tres ajustes se respetan y lo demás no se usa."""
    config.ajustes.parent.mkdir(parents=True, exist_ok=True)
    config.ajustes.write_text(json.dumps({
        "negocio": MARCA_ANTIGUA, "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 4,
    }), encoding="utf-8")
    estudio = Estudio(config)
    estado = estudio.publico()
    assert estado["ajustes"] == {
        "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 4.0, "tope_texto": "4,00 $",
    }
    assert "negocio" not in estado and "Mi tienda" not in json.dumps(estado, ensure_ascii=False)
    estudio.cambiar_ajustes({"tope_sesion_usd": 5})  # al guardar, el archivo queda solo con los tres ajustes
    assert json.loads(config.ajustes.read_text(encoding="utf-8")) == {
        "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 5.0,
    }
