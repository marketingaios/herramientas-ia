"""Paso 8: la clave de OpenRouter en `.env` (siempre el de la carpeta temporal, nunca el real)."""

from __future__ import annotations

import json
import stat
import sys

import pytest

from conftest import RAIZ
from estudio import clave as la_clave
from estudio.clave import ErrorClave
from estudio.estudio import ErrorEstudio, Estudio


@pytest.fixture
def env(config):
    assert config.env != RAIZ / ".env", "esta prueba no puede tocar el .env real"
    return config.env


def test_al_guardar_se_crea_el_env_con_una_sola_linea(env, clave_falsa):
    la_clave.guardar(env, clave_falsa)
    assert env.read_text(encoding="utf-8") == f"OPENROUTER_API_KEY={clave_falsa}\n"
    assert la_clave.leer(env) == clave_falsa
    assert [p.name for p in env.parent.iterdir() if p.name.startswith(".env")] == [".env"]  # sin restos temporales


@pytest.mark.skipif(sys.platform == "win32", reason="en Windows los permisos van por otro lado")
def test_el_env_queda_legible_solo_por_el_usuario(env, clave_falsa):
    la_clave.guardar(env, clave_falsa)
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    env.chmod(0o644)  # aunque alguien lo abra de más, al volver a guardar se cierra
    la_clave.guardar(env, clave_falsa + "9")
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_solo_cambia_su_linea_y_deja_las_demas(env, clave_falsa):
    antes = "# claves de mis herramientas\nOTRA_CLAVE=abc123\n\nOPENROUTER_API_KEY=vieja-clave-0000\nexport ULTIMA='x y z'\n"
    env.write_text(antes, encoding="utf-8")
    la_clave.guardar(env, clave_falsa)
    assert env.read_text(encoding="utf-8") == antes.replace("vieja-clave-0000", clave_falsa)


def test_si_no_habia_linea_se_anade_al_final(env, clave_falsa):
    env.write_text("OTRA_CLAVE=abc123", encoding="utf-8")  # sin salto de línea al final
    la_clave.guardar(env, clave_falsa)
    assert env.read_text(encoding="utf-8") == f"OTRA_CLAVE=abc123\nOPENROUTER_API_KEY={clave_falsa}\n"


def test_respeta_los_saltos_de_linea_de_windows_y_las_lineas_repetidas(env, clave_falsa):
    env.write_bytes(b"UNO=1\r\nexport OPENROUTER_API_KEY=vieja-clave-1\r\nDOS=2\r\nOPENROUTER_API_KEY = vieja-clave-2\r\n")
    la_clave.guardar(env, clave_falsa)
    assert env.read_bytes() == f"UNO=1\r\nOPENROUTER_API_KEY={clave_falsa}\r\nDOS=2\r\n".encode()


def test_la_clave_se_lee_del_archivo_cada_vez(env, clave_falsa):
    assert la_clave.leer(env) is None
    la_clave.guardar(env, clave_falsa)
    assert la_clave.leer(env) == clave_falsa
    env.write_text('OTRA=1\nOPENROUTER_API_KEY="cambiada-a-mano-1234"\n', encoding="utf-8")  # alguien la cambia fuera
    assert la_clave.leer(env) == "cambiada-a-mano-1234"
    env.write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")
    assert la_clave.leer(env) is None


def test_la_mascara_solo_deja_ver_los_cuatro_ultimos(clave_falsa):
    visible = la_clave.mascara(clave_falsa)
    assert visible == "••••" + clave_falsa[-4:]
    assert len(visible) == 8 and clave_falsa[:-4] not in visible


@pytest.mark.parametrize(
    "mala",
    ["", "   ", "corta", "con espacio dentro 12345", "linea-uno-12345\nOTRA_VARIABLE=1", "con\ttabulador-12345",
     'con"comillas-12345', "con#almohadilla-12345", "con=igual-1234567", "x" * 401, None, 12345678, ["lista-123456"]],
)
def test_una_clave_que_no_parece_clave_no_se_guarda(env, mala):
    env.write_text("OTRA=1\n", encoding="utf-8")
    with pytest.raises(ErrorClave) as error:
        la_clave.guardar(env, mala)
    assert str(error.value) == "La clave no parece válida: cópiala entera, sin espacios."
    assert env.read_text(encoding="utf-8") == "OTRA=1\n"  # el archivo no se tocó


def test_se_aceptan_los_espacios_de_alrededor_al_copiar(env, clave_falsa):
    la_clave.guardar(env, f"  {clave_falsa}\n")
    assert la_clave.leer(env) == clave_falsa


def test_borrar_quita_solo_su_linea(env, clave_falsa):
    la_clave.borrar(env)  # sin archivo: no pasa nada
    assert not env.exists()

    env.write_text(f"UNO=1\nOPENROUTER_API_KEY={clave_falsa}\nDOS=2\n", encoding="utf-8")
    la_clave.borrar(env)
    assert env.read_text(encoding="utf-8") == "UNO=1\nDOS=2\n"

    la_clave.guardar(env, clave_falsa)
    env.write_text(f"OPENROUTER_API_KEY={clave_falsa}\n", encoding="utf-8")
    la_clave.borrar(env)
    assert not env.exists()  # si solo estaba la clave, no se deja un archivo vacío


def test_un_env_con_bytes_raros_no_se_estropea(env, clave_falsa):
    env.write_bytes(b"RARA=caf\xe9\nOPENROUTER_API_KEY=vieja-clave-0000\n")
    la_clave.guardar(env, clave_falsa)
    assert env.read_bytes() == b"RARA=caf\xe9\nOPENROUTER_API_KEY=" + clave_falsa.encode() + b"\n"


# --- Desde el estudio: lo que ve la página ------------------------------------------------------------------------


def test_la_pagina_solo_ve_la_mascara(config, clave_falsa):
    estudio = Estudio(config)
    assert estudio.publico()["clave"] == {"guardada": False, "mascara": None}

    estudio.guardar_clave(clave_falsa)
    estado = estudio.publico()
    assert estado["clave"] == {"guardada": True, "mascara": "••••" + clave_falsa[-4:]}
    assert clave_falsa not in json.dumps(estado, ensure_ascii=False)
    assert estudio.clave() == clave_falsa  # para llamar a OpenRouter sí se lee entera

    estudio.borrar_clave()
    assert estudio.publico()["clave"] == {"guardada": False, "mascara": None}
    assert not config.env.exists()


def test_una_clave_mala_desde_la_pagina_da_el_mensaje_sin_repetirla(config):
    estudio = Estudio(config)
    with pytest.raises(ErrorEstudio) as error:
        estudio.guardar_clave("una clave con espacios 123456")
    assert str(error.value) == "La clave no parece válida: cópiala entera, sin espacios."
    assert "123456" not in str(error.value)
    assert not config.env.exists()


def test_la_clave_no_se_escribe_en_ajustes_json(config, clave_falsa):
    estudio = Estudio(config)
    estudio.guardar_clave(clave_falsa)
    estudio.cambiar_ajustes({"tope_sesion_usd": 2, "modelo_escenas": "google/gemini-3-pro-image"})
    for archivo in config.datos.rglob("*"):
        if archivo.is_file():
            assert clave_falsa.encode() not in archivo.read_bytes(), f"la clave está en {archivo.name}"
    assert "OPENROUTER" not in config.ajustes.read_text(encoding="utf-8")
