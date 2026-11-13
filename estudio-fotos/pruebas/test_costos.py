"""Paso 10: el costo de las escenas. Estimación, tope de la sesión, límite de la clave y `gastos.jsonl`."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from estudio import costos
from estudio.costos import SinPresupuesto
from estudio.openrouter import Cliente, ErrorOpenRouter

RECOMENDADO = "google/gemini-nano-banana-2.1"
PRO = "google/gemini-3-pro-image"


# --- Importes ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "importe, texto",
    [(0.2, "0,20 $"), (0.04, "0,04 $"), (0.038, "0,038 $"), (0.076, "0,076 $"), (1, "1,00 $"), (2.0, "2,00 $"),
     (0.12, "0,12 $"), (0, "0,00 $"), (12.5, "12,50 $"), (0.19, "0,19 $"), (0.1234, "0,12 $")],
)
def test_formato_de_los_importes(importe, texto):
    assert costos.dolares(importe) == texto


# --- Estimación -------------------------------------------------------------------------------------------------------


def test_sin_escenas_hechas_la_estimacion_es_el_costo_de_partida(config):
    estimacion = costos.estimar(config.gastos, RECOMENDADO, 5)
    assert (estimacion.por_imagen, estimacion.total, estimacion.origen) == (0.04, 0.2, "partida")
    assert estimacion.texto() == "5 escenas · costo estimado 0,20 $ · ¿Generar?"  # el ejemplo de la ficha
    assert not config.gastos.exists()  # estimar no escribe nada


@pytest.mark.parametrize("modelo, partida", [
    ("google/gemini-nano-banana-2.1", 0.04), ("google/gemini-3.1-flash-lite-image", 0.04),
    ("google/gemini-3.1-flash-image", 0.07), ("google/gemini-3-pro-image", 0.14),
])
def test_costo_de_partida_de_cada_modelo(config, modelo, partida):
    assert costos.estimar(config.gastos, modelo, 1).total == partida
    assert costos.estimar(config.gastos, modelo, 3).total == pytest.approx(partida * 3)


def test_una_sola_escena_se_dice_en_singular(config):
    assert costos.estimar(config.gastos, PRO, 1).texto() == "1 escena · costo estimado 0,14 $ · ¿Generar?"


def test_con_escenas_hechas_la_estimacion_es_la_media_de_los_costos_reales(config):
    for real in (0.038, 0.038, 0.041):
        costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, real)
    estimacion = costos.estimar(config.gastos, RECOMENDADO, 5)
    assert estimacion.origen == "media"
    assert estimacion.por_imagen == pytest.approx(0.039)
    assert estimacion.total == pytest.approx(0.195)
    assert estimacion.texto() == "5 escenas · costo estimado 0,20 $ · ¿Generar?"


def test_la_media_es_la_de_cada_modelo(config):
    costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.038)
    costos.anotar_gasto(config.gastos, PRO, 0.14, 0.2)
    assert costos.estimar(config.gastos, RECOMENDADO, 2).total == pytest.approx(0.076)
    assert costos.estimar(config.gastos, PRO, 2).total == pytest.approx(0.4)
    otro = costos.estimar(config.gastos, "google/gemini-3.1-flash-image", 2)  # sin escenas de ese modelo
    assert (otro.total, otro.origen) == (0.14, "partida")


def test_la_media_cuenta_por_imagen(config):
    """Si una línea reúne varias imágenes, cada imagen pesa lo mismo."""
    costos.anotar_gasto(config.gastos, RECOMENDADO, 0.12, 0.09, imagenes=3)
    costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.05)
    assert costos.estimar(config.gastos, RECOMENDADO, 1).por_imagen == pytest.approx(0.035)


def test_un_gastos_jsonl_roto_no_estropea_la_estimacion(config):
    costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.038)
    with open(config.gastos, "a", encoding="utf-8") as archivo:
        archivo.write("esto no es json\n")
        archivo.write('["una", "lista"]\n\n')
        archivo.write(json.dumps({"modelo": RECOMENDADO, "imagenes": 0, "costo_usd": 9}) + "\n")
        archivo.write(json.dumps({"modelo": RECOMENDADO, "imagenes": 1, "costo_usd": "mucho"}) + "\n")
        archivo.write(json.dumps({"modelo": RECOMENDADO, "imagenes": 1, "costo_usd": -5}) + "\n")
        archivo.write(json.dumps({"modelo": RECOMENDADO, "imagenes": True, "costo_usd": 7}) + "\n")
        archivo.write(json.dumps({"modelo": RECOMENDADO, "imagenes": 1, "costo_usd": None}) + "\n")
    assert costos.estimar(config.gastos, RECOMENDADO, 1).por_imagen == pytest.approx(0.038)

    config.gastos.write_bytes(b"\xff\xfe\x00 nada legible")
    assert costos.estimar(config.gastos, RECOMENDADO, 1).origen == "partida"


def test_un_modelo_desconocido_no_se_estima(config):
    with pytest.raises(ValueError):
        costos.estimar(config.gastos, "otro/modelo", 1)


# --- gastos.jsonl -----------------------------------------------------------------------------------------------------


def test_cada_gasto_es_una_linea_json_con_los_cinco_campos_de_la_ficha(config):
    primera = costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.038)
    costos.anotar_gasto(config.gastos, PRO, 0.14, 0.151)
    lineas = config.gastos.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    gasto = json.loads(lineas[0])
    assert gasto == primera
    assert list(gasto) == ["ts", "modelo", "imagenes", "costo_estimado_usd", "costo_usd"]
    assert (gasto["modelo"], gasto["imagenes"], gasto["costo_estimado_usd"], gasto["costo_usd"]) == (RECOMENDADO, 1, 0.04, 0.038)
    assert json.loads(lineas[1])["costo_usd"] == 0.151


def test_la_fecha_va_en_iso_8601_y_en_utc(config):
    gasto = costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.038)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", gasto["ts"])
    momento = datetime.fromisoformat(gasto["ts"].replace("Z", "+00:00"))
    assert abs(datetime.now(timezone.utc) - momento) < timedelta(seconds=5)

    # Una hora local (aquí, UTC-5) se anota convertida a UTC.
    local = datetime(2026, 11, 13, 10, 30, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, 0.038, ahora=local)["ts"] == "2026-11-13T15:30:00Z"


def test_si_openrouter_no_informa_el_costo_se_anota_sin_inventarlo(config):
    gasto = costos.anotar_gasto(config.gastos, RECOMENDADO, 0.04, None)
    assert gasto["costo_usd"] is None and gasto["costo_estimado_usd"] == 0.04
    assert costos.estimar(config.gastos, RECOMENDADO, 1).origen == "partida"  # y no entra en la media


def test_gastos_jsonl_se_escribe_en_la_carpeta_de_la_herramienta(config):
    from conftest import CARPETA

    assert config.gastos.name == "gastos.jsonl" and config.gastos.parent == config.datos
    assert config.gastos != CARPETA / "gastos.jsonl"  # en las pruebas, nunca el de verdad
    from estudio.config import Config

    assert Config().gastos == CARPETA / "gastos.jsonl"


# --- Tope de la sesión y límite de la clave -------------------------------------------------------------------------------


def test_si_la_estimacion_supera_lo_que_queda_del_tope_no_se_gasta():
    with pytest.raises(SinPresupuesto) as error:
        costos.comprobar_tope(0.2, tope=1.0, gastado=0.9)
    assert error.value.motivo == "tope"
    assert str(error.value) == (
        "Esto costaría 0,20 $ y en esta sesión te quedan 0,10 $. Sube el tope en Ajustes o genera menos escenas."
    )


def test_lo_que_cabe_justo_pasa():
    costos.comprobar_tope(0.2, tope=1.0, gastado=0.8)  # 1,0 − 0,8 no es exactamente 0,2 para el procesador
    costos.comprobar_tope(1.0, tope=1.0, gastado=0.0)
    costos.comprobar_tope(0.04, tope=0.04, gastado=0.0)
    costos.comprobar_tope(0.3, tope=1.0, gastado=0.1 + 0.2 + 0.4)
    with pytest.raises(SinPresupuesto):
        costos.comprobar_tope(0.201, tope=1.0, gastado=0.8)


def test_con_el_tope_ya_gastado_el_mensaje_dice_que_no_queda_nada():
    with pytest.raises(SinPresupuesto) as error:
        costos.comprobar_tope(0.04, tope=1.0, gastado=1.02)
    assert "te quedan 0,00 $" in str(error.value)


def test_si_la_estimacion_supera_lo_que_queda_en_la_clave_no_se_gasta():
    with pytest.raises(SinPresupuesto) as error:
        costos.comprobar_clave(0.2, restante=0.05)
    assert error.value.motivo == "clave"
    assert str(error.value) == (
        "Esto costaría 0,20 $ y a tu clave de OpenRouter le quedan 0,05 $. "
        "Sube el límite de la clave en OpenRouter o genera menos escenas."
    )
    costos.comprobar_clave(0.2, restante=0.2)
    costos.comprobar_clave(0.2, restante=None)  # una clave sin límite pasa


# --- Con el simulador: qué se llama y qué no --------------------------------------------------------------------------


@pytest.fixture
def cliente(simulador, clave_falsa):
    return Cliente(simulador.url, lambda: clave_falsa, dormir=lambda segundos: None)


def test_con_el_tope_superado_no_se_llama_a_openrouter(cliente, simulador):
    with pytest.raises(SinPresupuesto) as error:
        costos.antes_de_gastar(0.2, tope=1.0, gastado=0.95, probar=cliente.probar)
    assert error.value.motivo == "tope"
    assert simulador.peticiones == []  # ni /key ni /images


def test_si_cabe_en_el_tope_se_pregunta_por_la_clave_y_no_se_gasta_todavia(cliente, simulador):
    costos.antes_de_gastar(0.2, tope=1.0, gastado=0.0, probar=cliente.probar)
    assert [(p["metodo"], p["ruta"]) for p in simulador.peticiones] == [("GET", "/api/v1/key")]


def test_si_a_la_clave_no_le_queda_bastante_no_se_gasta(cliente, simulador):
    simulador.llave = {"label": "pruebas", "limit": 2.0, "limit_remaining": 0.1, "usage": 1.9}
    with pytest.raises(SinPresupuesto) as error:
        costos.antes_de_gastar(0.2, tope=1.0, gastado=0.0, probar=cliente.probar)
    assert error.value.motivo == "clave" and "le quedan 0,10 $" in str(error.value)
    assert simulador.imagenes_pedidas() == []


def test_una_clave_sin_limite_pasa(cliente, simulador):
    simulador.llave = {"label": "pruebas", "limit": None, "limit_remaining": None, "usage": 0.5}
    costos.antes_de_gastar(0.2, tope=1.0, gastado=0.0, probar=cliente.probar)
    assert simulador.imagenes_pedidas() == []


def test_si_la_clave_no_vale_se_dice_antes_de_gastar(simulador):
    cliente = Cliente(simulador.url, lambda: "sk-or-v1-una-clave-que-no-es", dormir=lambda segundos: None)
    with pytest.raises(ErrorOpenRouter) as error:
        costos.antes_de_gastar(0.2, tope=1.0, gastado=0.0, probar=cliente.probar)
    assert error.value.tipo == "clave"
    assert simulador.imagenes_pedidas() == []
