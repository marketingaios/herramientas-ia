"""Paso 1: la carpeta común de herramientas-ia y el proyecto con las versiones fijadas."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

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
        "estudio-fotos/README.md",
        "estudio-fotos/CAMBIOS.md",
        "estudio-fotos/PRUEBAS.md",
        "estudio-fotos/REVISION.md",
        "estudio-fotos/plataformas.json",
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


# --- Paso 19: los documentos --------------------------------------------------------------------------------------


def test_el_comando_de_arranque_esta_en_agents_md_y_en_el_readme():
    """Un solo comando, el mismo en Mac, Linux y Windows, escrito en los dos sitios (y en la página de inicio)."""
    for documento in (RAIZ / "AGENTS.md", CARPETA / "README.md", RAIZ / "inicio" / "index.html"):
        assert COMANDO in _texto(documento), documento.name
    # Y es el comando de verdad: el paquete `estudio` se arranca con `python -m estudio` desde `estudio-fotos`.
    assert (CARPETA / "estudio" / "__main__.py").is_file()


def test_el_readme_dice_como_se_abre_y_como_se_usa():
    texto = _texto(CARPETA / "README.md")
    for parte in (
        "## Cómo se abre", "«Abre el estudio de fotos»", "http://127.0.0.1:8601", "Ctrl",
        "## Cómo se usa", "**Fotos**", "**Resultados**", "**Ajustes**",
        "### 1 · Sube tus fotos", "### 2 · Recortes, antes y después", "### 3 · Fondo blanco y medidas",
        "### 4 · Escenas con IA (opcional)", "### Resultados", "## Ajustes", "## Dónde queda cada cosa",
        "## Cómo saber si funciona bien: seis controles", "## Privacidad", "## Si algo falla", "## Si usas Windows",
        "«5 escenas · costo estimado 0,20 $ · ¿Generar?»", "«Conexión correcta · límite 2,00 $ · usado 0,12 $»",
        "«Para redes y fotos secundarias»", "`resumen.csv`", "`plataformas.json`", "`gastos.jsonl`",
    ):
        assert parte in texto, parte


def test_la_tabla_de_plataformas_del_readme_coincide_con_plataformas_json():
    plataformas = json.loads(_texto(CARPETA / "plataformas.json"))["plataformas"]
    lineas = _texto(CARPETA / "README.md").splitlines()
    assert len(plataformas) == 8
    for plataforma in plataformas:
        fila = next(linea for linea in lineas if linea.startswith(f"| {plataforma['nombre']} |"))
        assert f"{plataforma['ancho']}×{plataforma['alto']}" in fila, fila
        assert f"| {plataforma['porcentaje']} % |" in fila, fila
        peso = plataforma["peso_maximo_kb"]
        esperado = "no publica uno" if peso is None else (f"{peso // 1000} MB" if peso >= 1000 else f"{peso} KB")
        assert fila.rstrip(" |").endswith(esperado), fila
        if plataforma.get("sin_ampliar"):
            assert f"{plataforma['ancho_minimo']}×{plataforma['alto_minimo']}" in fila and "sin ampliar" in fila


def test_los_mensajes_del_readme_son_los_de_la_herramienta():
    from estudio.openrouter import MENSAJES
    from estudio.recorte import mensaje_descarga
    from estudio.__main__ import mensaje_puerto_ocupado

    texto = _texto(CARPETA / "README.md")
    for clave in ("sin_clave", "clave", "saldo", "generacion", "conexion"):
        assert f"«{MENSAJES[clave]}»" in texto, clave
    assert f"«{mensaje_puerto_ocupado(8601, 8602)}»" in texto
    assert "973 MB" in mensaje_descarga("birefnet-general") and "973 MB" in texto and "224 MB" in texto


def test_cambios_md_cuenta_la_version_1():
    texto = _texto(CARPETA / "CAMBIOS.md")
    proyecto = tomllib.loads(_texto(CARPETA / "pyproject.toml"))
    assert texto.startswith("# Cambios") and "## Versión 1" in texto
    assert proyecto["project"]["version"].startswith("1.")
    fila = next(linea for linea in _texto(RAIZ / "AGENTS.md").splitlines() if linea.startswith("| Estudio de fotos"))
    assert "| 1 |" in fila


def test_los_documentos_estan_en_espanol_y_sin_datos_personales():
    documentos = [ruta for ruta in CARPETA.glob("*.md") if ruta.name != "FICHA.md"] + [RAIZ / "AGENTS.md"]
    assert {"README.md", "CAMBIOS.md", "PLAN.md", "TAREAS.md", "PRUEBAS.md", "REVISION.md"} <= {ruta.name for ruta in documentos}
    for ruta in documentos:
        texto = _texto(ruta)
        assert str(Path.home()) not in texto, f"{ruta.name} lleva la ruta de la carpeta personal"
        assert "/Users/" not in texto and "/home/" not in texto, ruta.name
        assert "@" not in texto.replace("@AGENTS.md", ""), f"{ruta.name} lleva algo con forma de correo"
        assert "sk-or-v1-" not in texto, ruta.name
    for palabra in (" the ", " and ", "How to", "Usage"):
        assert palabra not in _texto(CARPETA / "README.md"), palabra
