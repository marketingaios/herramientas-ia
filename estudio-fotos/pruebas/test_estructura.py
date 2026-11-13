"""Paso 1: la carpeta común de herramientas-ia y el proyecto con las versiones fijadas."""

from __future__ import annotations

import shutil
import subprocess
import tomllib

import pytest

from conftest import CARPETA, RAIZ

ENLACE_FIRMA = "https://marketingaios.com/?origen=herramienta-estudio-fotos"
COMANDO = "uv run --directory estudio-fotos python -m estudio"


def _texto(ruta) -> str:
    return ruta.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "ruta",
    [
        "AGENTS.md",
        "CLAUDE.md",
        ".gitignore",
        "instrucciones.md",
        "estilo/estilo.css",
        "estilo/firma.html",
        "inicio/index.html",
        "marca/ismagit_negro.png",
        "estudio-fotos/FICHA.md",
        "estudio-fotos/PLAN.md",
        "estudio-fotos/TAREAS.md",
        "estudio-fotos/pyproject.toml",
        "estudio-fotos/uv.lock",
    ],
)
def test_los_archivos_existen(ruta):
    assert (RAIZ / ruta).is_file()


def test_la_ficha_guardada_es_la_ficha():
    assert _texto(CARPETA / "FICHA.md") == _texto(RAIZ / "instrucciones.md")


def test_claude_md_es_una_sola_linea():
    assert _texto(RAIZ / "CLAUDE.md").splitlines() == ["@AGENTS.md"]


def test_agents_md_dice_como_se_trabaja_y_como_se_abre():
    texto = _texto(RAIZ / "AGENTS.md")
    for parte in ("## Reglas fijas", "## Método", "## Herramientas", "«Abre …»", "segundo plano", "127.0.0.1"):
        assert parte in texto
    cabecera = next(linea for linea in texto.splitlines() if linea.startswith("| Herramienta"))
    for columna in ("Herramienta", "Carpeta", "Versión", "Dirección", "Cómo abrirla", "Mac", "Linux", "Windows"):
        assert columna in cabecera
    fila = next(linea for linea in texto.splitlines() if linea.startswith("| Estudio de fotos"))
    assert "`estudio-fotos/`" in fila and "http://127.0.0.1:8601" in fila and COMANDO in fila


def test_gitignore_cubre_lo_pedido():
    lineas = set(_texto(RAIZ / ".gitignore").splitlines())
    for patron in (".env", "modelos/", "*/trabajo/", "*/salidas/", "gastos.jsonl", ".venv/", "__pycache__/"):
        assert patron in lineas


@pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")
@pytest.mark.parametrize(
    "ruta",
    [
        ".env",
        "modelos/models/birefnet-general/birefnet-general.onnx",
        "estudio-fotos/trabajo/abc/vista.jpg",
        "estudio-fotos/salidas/2026-11-13_1200/recortes/foto_recorte.png",
        "estudio-fotos/gastos.jsonl",
        "estudio-fotos/ajustes.json",
        "estudio-fotos/.venv/pyvenv.cfg",
        "estudio-fotos/estudio/__pycache__/config.cpython-312.pyc",
    ],
)
def test_git_deja_fuera_lo_privado(ruta):
    resultado = subprocess.run(["git", "check-ignore", "-q", ruta], cwd=RAIZ)
    assert resultado.returncode == 0, f"git no está dejando fuera {ruta}"


def test_no_hay_ningun_env_de_ejemplo():
    assert not list(RAIZ.glob(".env.*")) and not list(CARPETA.glob(".env*"))


def test_todas_las_dependencias_tienen_la_version_fijada():
    proyecto = tomllib.loads(_texto(CARPETA / "pyproject.toml"))
    dependencias = list(proyecto["project"]["dependencies"])
    for grupo in proyecto["dependency-groups"].values():
        dependencias.extend(grupo)
    assert len(dependencias) >= 9
    for dependencia in dependencias:
        assert "==" in dependencia, f"{dependencia} no tiene la versión fijada"
    assert 'name = "rembg"' in _texto(CARPETA / "uv.lock")


def test_la_firma_esta_en_la_pagina_de_inicio():
    for pagina in (RAIZ / "inicio" / "index.html", RAIZ / "estilo" / "firma.html"):
        texto = _texto(pagina)
        assert ENLACE_FIRMA in texto
        assert "Hecho con la guía de Ismagit" in texto
        assert "marca/ismagit_negro.png" in texto


def test_la_pagina_de_inicio_lista_la_herramienta():
    texto = _texto(RAIZ / "inicio" / "index.html")
    assert "Estudio de fotos de producto" in texto
    assert "http://127.0.0.1:8601" in texto
    assert COMANDO in texto
