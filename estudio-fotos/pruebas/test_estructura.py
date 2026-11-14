"""Paso 1: la carpeta común de herramientas-ia y el proyecto con las versiones fijadas."""

from __future__ import annotations

import json
import re
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
        "marca/ismagit_logo.png",
        "marca/fuentes/OFL.txt",
        "estilo/fuentes/geist-latin.woff2",
        "estilo/fuentes/geist-mono-latin.woff2",
        "estilo/fuentes/OFL.txt",
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
        assert "marca/ismagit_logo.png" in texto


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


def test_cambios_md_cuenta_las_versiones_1_y_1_1():
    texto = _texto(CARPETA / "CAMBIOS.md")
    assert texto.startswith("# Cambios")
    titulos = re.findall(r"^## (Versión [\d.]+) · \d+ de \w+ de \d{4}$", texto, re.M)
    assert titulos == ["Versión 1.1", "Versión 1"]  # la última, arriba
    la_1_1, la_1 = texto.split("## Versión 1 · ")[0], texto.split("## Versión 1 · ")[1]
    # La 1.1 cuenta los seis cambios del punto 13 de la ficha.
    for parte in ("Diseño de Ismagit", "Sin marca del negocio", "«Fondo liso de un color»", "Muestras", "Para Mac y Windows",
                  "`estilo/fuentes/`", "Si vienes de la versión 1", "`logo_negocio.png`", "Para la versión siguiente"):
        assert parte in la_1_1, parte
    # La entrada de la versión 1 sigue como estaba.
    for parte in ("La primera versión, hecha con la ficha 1", "**Qué trae**", "**Lo que esta versión no hace**", "**Para la versión siguiente**"):
        assert parte in la_1, parte
    # Lo que quedó pendiente en la versión 1 sigue anotado en la 1.1.
    pendientes = [linea for linea in la_1.split("**Para la versión siguiente**")[1].splitlines() if linea.startswith("- ")]
    assert len(pendientes) == 3 and all(pendiente in la_1_1 for pendiente in pendientes)


def test_la_version_es_la_1_1_en_todos_los_sitios():
    from estudio import VERSION

    assert VERSION == "1.1"
    assert tomllib.loads(_texto(CARPETA / "pyproject.toml"))["project"]["version"] == "1.1.0"
    assert 'name = "estudio-fotos"\nversion = "1.1.0"' in _texto(CARPETA / "uv.lock")
    fila = next(linea for linea in _texto(RAIZ / "AGENTS.md").splitlines() if linea.startswith("| Estudio de fotos"))
    assert "| 1.1 |" in fila and "| 1 |" not in fila
    inicio = " ".join(_texto(RAIZ / "inicio" / "index.html").split())
    assert "Versión 1.1 · Para abrirla:" in inicio and "Versión 1 ·" not in inicio
    assert _texto(CARPETA / "README.md").splitlines()[2].startswith("Versión 1.1 · ")
    assert _texto(CARPETA / "FICHA.md").splitlines()[2] == "**Construyamos con IA · ficha 1 · versión 1.1 · noviembre de 2026 · guía de Ismagit**"


def test_el_readme_es_el_de_la_version_1_1():
    texto = _texto(CARPETA / "README.md")
    junto = " ".join(texto.split())
    assert "Para Mac y Windows." in texto.splitlines()[2]
    assert "aún sin probar" not in texto and "se probó en Mac" not in texto
    # Para qué productos sirve, con sus dos avisos.
    assert texto.index("## Para qué productos sirve") < texto.index("## Cómo se abre")
    seccion = " ".join(texto.split("## Para qué productos sirve")[1].split("## ")[0].split())
    for parte in ("Para fotos de **objetos**", "No es para fotos de personas ni de modelos con la ropa puesta",
                  "los objetos **transparentes** (vidrio, plástico claro) y los bordes muy finos: revisa el recorte antes de publicar"):
        assert parte in seccion, parte
    # Las escenas: el fondo liso de un color, y la nota sin Google.
    assert "«Fondo liso de un color»" in texto and "un selector para elegir el color" in junto
    assert "Mercado Libre y Amazon piden fondo blanco en la foto principal." in junto
    assert "Amazon y Google piden" not in junto and "colores de tu marca, en exterior" not in junto
    # Ajustes, sin marca del negocio.
    ajustes = texto.split("\n## Ajustes\n")[1].split("\n## ")[0]
    assert re.findall(r"^- \*\*([^*]+)\*\*", ajustes, re.M) == ["Clave de OpenRouter", "Calidad del recorte", "Escenas con IA"]
    assert "Marca del negocio" not in texto and "color de acento" not in texto
    assert "| Tus ajustes (sin la clave) | `estudio-fotos/ajustes.json` |" in texto
    # Y qué pasa con lo que guardó la versión 1.
    assert "## Si vienes de la versión 1" in texto and "Tu logo original no se toca." in texto
    assert "tampoco las fuentes" in junto


def test_agents_md_describe_las_carpetas_comunes_de_la_ficha_1_1():
    texto = _texto(RAIZ / "AGENTS.md")
    comunes = texto.split("## Carpetas comunes")[1]
    for parte in ("`estilo/`", "el diseño de Ismagit", "`fuentes/`", "`firma.html`", "`marca/`: el logo de Ismagit y las fuentes Geist",
                  "`muestras/`: fotos de ejemplo hechas con IA.", "`modelos/`", "`inicio/index.html`"):
        assert parte in comunes, parte
    assert "- **Diseño**: todas las herramientas llevan el de Ismagit" in texto


def test_no_queda_el_negocio_de_ejemplo_de_la_version_1():
    """Ni su nombre, ni su logo, ni sus colores, en ningún archivo del proyecto: código, pruebas, páginas y documentos.

    El nombre se arma aquí por partes para que esta prueba no lo lleve escrito. No se miran las carpetas de datos de
    quien usa la herramienta (sus ajustes, sus resultados), ni nunca el archivo de la clave.
    """
    numero = "26" + "00"
    nombre = re.compile(rf"caf(e|é|É|Ã©|\\u00e9)[\s_\-·]*{numero}".encode("utf-8"), re.I)
    colores = [("#1F" + "3B2D").encode(), ("#C8" + "A04B").encode(), ("#C8" + "A26B").encode(), ("#C4" + "622D").encode()]
    fuera = {".git", ".venv", "venv", "modelos", "trabajo", "salidas", ".pruebas-tmp", ".navegadores", "__pycache__",
             ".pytest_cache", "node_modules"}
    de_datos = {"ajustes.json", "gastos.jsonl", "medicion.json", "logo_negocio.png"}  # lo que escribe la herramienta al usarla
    mirados = 0
    for ruta in RAIZ.rglob("*"):
        partes = ruta.relative_to(RAIZ).parts
        if not ruta.is_file() or fuera & set(partes) or ruta.name.startswith(".env") or ruta.name in de_datos:
            continue
        assert not nombre.search(ruta.name.encode("utf-8")), f"el nombre del archivo {ruta.name}"
        if ruta.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".woff2", ".zip", ".onnx"} or ruta.name == "uv.lock":
            continue  # las fotos y las fuentes no son texto; `uv.lock` lo escribe uv (son nombres y huellas)
        datos = ruta.read_bytes()
        mirados += 1
        assert not nombre.search(datos), f"{'/'.join(partes)} todavía nombra al negocio de ejemplo"
        for color in colores:
            assert color not in datos.upper(), f"{'/'.join(partes)} todavía lleva un color del negocio de ejemplo"
    assert mirados > 60
    # Tampoco quedan su logo ni sus tres fotos: en `marca/` y `muestras/` no hay nada más que lo de la guía.
    assert sorted(p.name for p in (RAIZ / "muestras").iterdir() if not p.name.startswith(".")) == [
        "bolsa_mesa.jpg", "bolso.jpg", "camiseta.jpg", "frasco_vidrio.jpg", "taza_logo.jpg", "zapatilla.jpg"]
    de_marca = {p.name for p in (RAIZ / "marca").iterdir() if not p.name.startswith(".")}
    assert {"ismagit_logo.png", "fuentes"} <= de_marca <= {"ismagit_logo.png", "fuentes", "ismagit_blanco.png", "ismagit_negro.png"}


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
