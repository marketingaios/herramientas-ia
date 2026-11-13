"""Paso 2: las plataformas de plataformas.json, con los valores de la ficha."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import CARPETA
from estudio.plataformas import ErrorPlataformas, cargar

# (id, nombre, ancho, alto, porcentaje, peso máximo en KB) tal como están en la tabla 4.3 de la ficha.
FICHA = [
    ("mercadolibre", "Mercado Libre", 1200, 1200, 95, 10_000),
    ("amazon", "Amazon", 2000, 2000, 85, None),
    ("shopify", "Shopify", 2048, 2048, 85, 20_000),
    ("tiendanube", "Tiendanube", 1280, 1280, 85, 500),
    ("instagram", "Instagram (feed)", 1080, 1350, 80, None),
    ("catalogo-meta", "Catálogo de Facebook e Instagram", 1024, 1024, 85, 8_000),
    ("whatsapp", "WhatsApp Business (catálogo)", 1024, 1024, 85, 8_000),
    ("google", "Google Merchant Center", 1500, 1500, 85, 16_000),
]


def test_estan_las_ocho_plataformas_de_la_ficha():
    plataformas = cargar(CARPETA / "plataformas.json")
    assert [(p.id, p.nombre, p.ancho, p.alto, p.porcentaje, p.peso_maximo_kb) for p in plataformas] == FICHA
    for plataforma in plataformas:
        assert plataforma.dice and plataforma.fuente


def test_amazon_baja_de_2000_a_1000_sin_ampliar():
    amazon = next(p for p in cargar(CARPETA / "plataformas.json") if p.id == "amazon")
    assert amazon.sin_ampliar is True
    assert (amazon.ancho_minimo, amazon.alto_minimo) == (1000, 1000)
    assert [p.id for p in cargar(CARPETA / "plataformas.json") if p.sin_ampliar] == ["amazon"]


def test_donde_no_se_publica_un_peso_no_se_pone_uno():
    por_id = {p.id: p for p in cargar(CARPETA / "plataformas.json")}
    assert por_id["amazon"].peso_maximo_bytes is None
    assert por_id["instagram"].peso_maximo_bytes is None
    assert por_id["tiendanube"].peso_maximo_bytes == 500_000
    assert por_id["amazon"].publica()["peso_maximo"] == "sin máximo publicado"
    assert por_id["mercadolibre"].publica()["peso_maximo"] == "10 MB"
    assert por_id["tiendanube"].publica()["peso_maximo"] == "500 KB"
    assert por_id["amazon"].publica()["medida"] == "de 1000×1000 a 2000×2000, sin ampliar"


def _con(tmp_path: Path, contenido) -> Path:
    ruta = tmp_path / "plataformas.json"
    ruta.write_text(contenido if isinstance(contenido, str) else json.dumps(contenido), encoding="utf-8")
    return ruta


def _una(**cambios) -> dict:
    base = {"id": "mitienda", "nombre": "Mi tienda", "ancho": 1000, "alto": 1000, "porcentaje": 85,
            "peso_maximo_kb": None}
    base.update(cambios)
    return {"plataformas": [base]}


def test_el_usuario_puede_anadir_su_plataforma(tmp_path):
    (plataforma,) = cargar(_con(tmp_path, _una(peso_maximo_kb=300)))
    assert plataforma.id == "mitienda" and plataforma.peso_maximo_bytes == 300_000


@pytest.mark.parametrize(
    "contenido",
    [
        "{ esto no es json",
        {"plataformas": []},
        {"otra": 1},
        _una(id="Con Espacios"),
        _una(id="../fuera"),
        _una(ancho=0),
        _una(alto="mil"),
        _una(ancho=50_000),
        _una(porcentaje=140),
        _una(peso_maximo_kb=-5),
        _una(nombre=""),
        {"plataformas": [_una()["plataformas"][0], _una()["plataformas"][0]]},
    ],
)
def test_un_archivo_con_errores_da_un_mensaje_claro_y_sin_rutas(tmp_path, contenido):
    with pytest.raises(ErrorPlataformas) as error:
        cargar(_con(tmp_path, contenido))
    mensaje = str(error.value)
    assert mensaje.startswith("plataformas.json tiene un error: ")
    assert str(tmp_path) not in mensaje and str(Path.home()) not in mensaje


def test_si_falta_el_archivo_tambien_se_dice(tmp_path):
    with pytest.raises(ErrorPlataformas) as error:
        cargar(tmp_path / "no_existe.json")
    assert str(tmp_path) not in str(error.value)
