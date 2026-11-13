"""Paso 5, con el modelo real (aparte: `pytest -m modelo`; la primera vez descarga el modelo).

Recorta las 5 fotos de `muestras/`, comprueba que cada recorte tiene un producto (la máscara ocupa entre el 5 % y el
95 % de la foto) y anota el tiempo por foto.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from conftest import MUESTRAS, RAIZ
from estudio.recorte import RecortadorRembg, recortar, ruta_modelo
from estudio.subidas import abrir_normalizada

pytestmark = pytest.mark.modelo

MODELO = "birefnet-general"
FOTOS = sorted(MUESTRAS.glob("*.jpg"))


def _carpetas_personales() -> dict:
    """Lo que hay en las carpetas donde rembg guardaría los modelos por su cuenta (sin abrir nada)."""
    estado = {}
    for carpeta in (Path.home() / ".u2net", Path.home() / ".rembg"):
        estado[carpeta.name] = (
            sorted((p.relative_to(carpeta).as_posix(), p.stat().st_mtime_ns) for p in carpeta.rglob("*"))
            if carpeta.exists()
            else None
        )
    return estado


@pytest.fixture(scope="module")
def recortes(tmp_path_factory):
    antes = _carpetas_personales()
    recortador = RecortadorRembg(MODELO, RAIZ / "modelos")
    recortador.descargar()
    inicio = time.perf_counter()
    recortador.preparar()
    preparar = time.perf_counter() - inicio

    resultados = {}
    for foto in FOTOS:
        imagen = abrir_normalizada(foto)
        inicio = time.perf_counter()
        resultado = recortar(imagen, recortador)
        resultados[foto.name] = (resultado, time.perf_counter() - inicio, imagen.size)

    informe = {
        "modelo": MODELO,
        "proveedores": recortador.proveedores_activos(),
        "preparar_s": round(preparar, 1),
        "fotos": {
            nombre: {"segundos": round(segundos, 1), "cobertura": round(r.cobertura * 100, 1)}
            for nombre, (r, segundos, _) in resultados.items()
        },
    }
    informe["media_s"] = round(sum(f["segundos"] for f in informe["fotos"].values()) / len(FOTOS), 1)
    (tmp_path_factory.getbasetemp() / "modelo_real.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nMODELO REAL:", json.dumps(informe, ensure_ascii=False))
    return {"resultados": resultados, "recortador": recortador, "antes": antes}


def test_hay_cinco_muestras():
    assert len(FOTOS) == 5


@pytest.mark.parametrize("foto", [f.name for f in FOTOS])
def test_cada_recorte_tiene_un_producto(recortes, foto):
    resultado, segundos, medida = recortes["resultados"][foto]
    assert 0.05 <= resultado.cobertura <= 0.95, f"la máscara ocupa el {resultado.cobertura:.0%} de la foto"
    assert resultado.imagen.mode == "RGBA" and resultado.imagen.size == medida
    alfa = np.asarray(resultado.imagen.getchannel("A"))
    # Un recorte de verdad: casi todo es fondo transparente o producto opaco, con un borde fino entre los dos.
    medio = ((alfa > 0) & (alfa < 255)).mean()
    assert medio < 0.03, f"demasiada zona medio transparente: {medio:.1%}"
    assert segundos < 120


def test_el_modelo_esta_en_la_carpeta_modelos_y_no_se_toco_la_carpeta_personal(recortes):
    assert ruta_modelo(RAIZ / "modelos", MODELO).is_file()
    assert ruta_modelo(RAIZ / "modelos", MODELO).stat().st_size > 900_000_000
    assert _carpetas_personales() == recortes["antes"]


def test_la_sesion_usa_el_modelo_pedido_por_su_nombre(recortes):
    recortador = recortes["recortador"]
    assert recortador.modelo == MODELO
    assert recortador._sesion.model_name == MODELO
    assert "bria" not in type(recortador._sesion).__name__.lower()
    assert "CPUExecutionProvider" in recortador.proveedores_activos()
