"""Paso 8: los ajustes del negocio (`ajustes.json` de la carpeta temporal) y el logo."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import ayudas
from conftest import RAIZ
from estudio import ajustes as los_ajustes
from estudio import costos
from estudio.estudio import ErrorEstudio, Estudio

LOGO_CAFE = RAIZ / "marca" / "cafe2600_logo.png"


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
    ajustes = estudio.publico()["ajustes"]
    assert ajustes == {
        "calidad_recorte": "automatica",
        "modelo_escenas": "google/gemini-nano-banana-2.1",
        "tope_sesion_usd": 1.0,
        "tope_texto": "1,00 $",
    }
    negocio = estudio.publico()["negocio"]
    assert negocio["nombre"] == "" and negocio["logo"] is None
    assert negocio["color_principal"].startswith("#") and negocio["color_acento"].startswith("#")


# --- Guardar ----------------------------------------------------------------------------------------------------------


def test_los_ajustes_se_guardan_en_ajustes_json_y_se_recuperan(estudio, config):
    estudio.cambiar_ajustes({
        "negocio": {"nombre": "  Café   2600 ", "color_principal": "#1f3b2d", "color_acento": "#C8A26B"},
        "calidad_recorte": "rapida",
        "modelo_escenas": "google/gemini-3-pro-image",
        "tope_sesion_usd": 2.5,
    })
    guardado = json.loads(config.ajustes.read_text(encoding="utf-8"))
    assert guardado == {
        "negocio": {"nombre": "Café 2600", "color_principal": "#1F3B2D", "color_acento": "#C8A26B"},
        "calidad_recorte": "rapida",
        "modelo_escenas": "google/gemini-3-pro-image",
        "tope_sesion_usd": 2.5,
    }
    assert "clave" not in config.ajustes.read_text(encoding="utf-8").lower()

    otro = Estudio(config)  # como si se reiniciara la herramienta
    assert otro.publico()["negocio"]["nombre"] == "Café 2600"
    assert otro.publico()["ajustes"]["tope_texto"] == "2,50 $"
    assert otro.publico()["modelo"]["etiqueta"] == "Modo rápido"


def test_se_puede_cambiar_un_solo_ajuste(estudio):
    estudio.cambiar_ajustes({"negocio": {"nombre": "Café 2600"}})
    estudio.cambiar_ajustes({"tope_sesion_usd": 3})
    estudio.cambiar_ajustes({"negocio": {"color_acento": "#B5F22A"}})
    estado = estudio.publico()
    assert (estado["negocio"]["nombre"], estado["negocio"]["color_acento"]) == ("Café 2600", "#B5F22A")
    assert estado["ajustes"]["tope_sesion_usd"] == 3.0 and estado["ajustes"]["calidad_recorte"] == "automatica"


def test_la_calidad_del_recorte_cambia_el_modelo(estudio):
    estudio.cambiar_ajustes({"calidad_recorte": "maxima"})
    assert estudio.publico()["modelo"]["nombre"] == "birefnet-general"
    estudio.cambiar_ajustes({"calidad_recorte": "rapida"})
    assert (estudio.publico()["modelo"]["nombre"], estudio.publico()["modelo"]["total_mb"]) == ("birefnet-general-lite", 224)


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"negocio": {"color_principal": "rojo"}}, "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."),
        ({"negocio": {"color_acento": "#12"}}, "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."),
        ({"negocio": {"color_acento": "#GGGGGG"}}, "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."),
        ({"negocio": {"color_principal": "#1F3B2D; background: url(http://example.com)"}}, "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."),
        ({"negocio": {"color_principal": 123456}}, "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."),
        ({"negocio": {"nombre": "x" * 61}}, "El nombre del negocio puede tener hasta 60 caracteres."),
        ({"negocio": "Café"}, "Los datos del negocio no tienen la forma esperada."),
        ({"calidad_recorte": "turbo"}, "La calidad del recorte debe ser Automática, Máxima o Rápida."),
        ({"modelo_escenas": "openai/otro-modelo"}, "Ese modelo de escenas no está en la lista."),
        ({"modelo_escenas": ""}, "Ese modelo de escenas no está en la lista."),
        ({"tope_sesion_usd": -1}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": 5000}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": "mucho"}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": float("nan")}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": True}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ("no es un objeto", "Los ajustes no tienen la forma esperada."),
    ],
)
def test_un_ajuste_que_no_vale_se_rechaza_y_no_se_guarda_nada(estudio, config, cambios, mensaje):
    antes = estudio.publico()
    with pytest.raises(ErrorEstudio) as error:
        estudio.cambiar_ajustes(cambios)
    assert str(error.value) == mensaje
    assert not config.ajustes.exists()
    assert estudio.publico()["ajustes"] == antes["ajustes"] and estudio.publico()["negocio"] == antes["negocio"]


def test_el_nombre_del_negocio_se_guarda_como_texto_sin_caracteres_de_control(estudio):
    estudio.cambiar_ajustes({"negocio": {"nombre": "<b>Café</b>\u0000‮ & Tostadores\n"}})
    assert estudio.publico()["negocio"]["nombre"] == "<b>Café</b> & Tostadores"  # la página lo escribe como texto


def test_un_ajustes_json_roto_no_impide_arrancar(config):
    config.ajustes.parent.mkdir(parents=True, exist_ok=True)
    config.ajustes.write_text("{ roto", encoding="utf-8")
    assert Estudio(config).publico()["ajustes"]["tope_sesion_usd"] == 1.0

    config.ajustes.write_text(json.dumps({
        "negocio": {"nombre": "Café 2600", "color_principal": "javascript:alert(1)"},
        "modelo_escenas": "modelo/desconocido", "tope_sesion_usd": 4, "calidad_recorte": "maxima",
    }), encoding="utf-8")
    estado = Estudio(config).publico()
    assert estado["ajustes"]["tope_sesion_usd"] == 4.0 and estado["ajustes"]["calidad_recorte"] == "maxima"
    assert estado["ajustes"]["modelo_escenas"] == "google/gemini-nano-banana-2.1"  # el desconocido vuelve al de fábrica
    assert estado["negocio"]["color_principal"] == los_ajustes.POR_DEFECTO["negocio"]["color_principal"]


# --- Colores ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "color, texto",
    [("#1F3B2D", "#FFFFFF"), ("#000000", "#FFFFFF"), ("#1F2937", "#FFFFFF"), ("#B5F22A", "#111827"),
     ("#FFFFFF", "#111827"), ("#F4E9D8", "#111827")],
)
def test_el_texto_se_lee_sobre_los_colores_de_la_marca(color, texto):
    assert los_ajustes.color_sobre(color) == texto


def test_la_pagina_recibe_tambien_el_color_del_texto(estudio):
    estudio.cambiar_ajustes({"negocio": {"color_principal": "#1F3B2D", "color_acento": "#B5F22A"}})
    negocio = estudio.publico()["negocio"]
    assert (negocio["sobre_principal"], negocio["sobre_acento"]) == ("#FFFFFF", "#111827")


# --- Logo -------------------------------------------------------------------------------------------------------------


def _subida(tmp_path, datos: bytes):
    ruta = tmp_path / "logo-subido"
    ruta.write_bytes(datos)
    return ruta


def test_el_logo_de_cafe_2600_se_guarda_como_png_pequeno(estudio, config, tmp_path):
    estudio.guardar_logo(_subida(tmp_path, LOGO_CAFE.read_bytes()))
    assert config.logo.name == "logo_negocio.png" and config.logo.parent == config.datos
    with Image.open(config.logo) as logo:
        assert logo.format == "PNG" and max(logo.size) == 600 and logo.mode == "RGBA"
    assert estudio.publico()["negocio"]["logo"].startswith("/api/logo?v=")

    estudio.quitar_logo()
    assert not config.logo.exists() and estudio.publico()["negocio"]["logo"] is None
    estudio.quitar_logo()  # quitarlo dos veces no es un error


@pytest.mark.parametrize(
    "datos, mensaje",
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "El logo debe ser una imagen JPG, PNG o WEBP."),
        (b"texto cualquiera", "El logo debe ser una imagen JPG, PNG o WEBP."),
        (b"GIF89a" + b"\x00" * 100, "El logo debe ser una imagen JPG, PNG o WEBP."),
        (b"\x89PNG\r\n\x1a\n" + b"basura" * 100, "No se puede abrir este logo: puede estar dañado."),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 300_000), "El logo pesa 5,3 MB: el máximo es 5."),
    ],
)
def test_un_logo_que_no_vale_se_rechaza(estudio, config, tmp_path, datos, mensaje):
    with pytest.raises(ErrorEstudio) as error:
        estudio.guardar_logo(_subida(tmp_path, datos))
    assert str(error.value) == mensaje
    assert not config.logo.exists()


def test_el_logo_no_se_guarda_tal_como_llega(estudio, config, tmp_path):
    """Se vuelve a crear con Pillow: lo que venga pegado al archivo (metadatos, bytes de más) no se conserva."""
    original = ayudas.foto(900, 300, "PNG") + b"<script>alert('pegado al final')</script>"
    estudio.guardar_logo(_subida(tmp_path, original))
    guardado = config.logo.read_bytes()
    assert b"script" not in guardado and guardado != original
