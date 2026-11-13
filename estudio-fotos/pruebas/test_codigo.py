"""Paso 12: comprobaciones sobre el propio código (sin ejecutarlo) y sobre los vigilantes de las pruebas."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

import conftest
from conftest import CARPETA, RAIZ

CODIGO = sorted((CARPETA / "estudio").glob("*.py"))
PRUEBAS = sorted((CARPETA / "pruebas").glob("*.py"))

# Carpetas que no son código de la herramienta (entornos, modelos, temporales y resultados).
FUERA = {".git", ".venv", "venv", "modelos", "trabajo", "salidas", ".pruebas-tmp", ".navegadores", "__pycache__",
         ".pytest_cache", "node_modules"}


def _lee(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _archivos_del_proyecto() -> list[Path]:
    """Los archivos de texto de `herramientas-ia`, sin entrar en entornos ni resultados, y sin abrir el `.env`."""
    archivos = []
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or FUERA & set(ruta.relative_to(RAIZ).parts):
            continue
        if ruta.name.startswith(".env") or ruta.stat().st_size > 2_000_000:
            continue
        archivos.append(ruta)
    return archivos


def test_hay_codigo_que_comprobar():
    assert len(CODIGO) >= 15 and len(PRUEBAS) >= 15


@pytest.mark.parametrize("prohibido", [r"shell\s*=\s*True", r"\beval\s*\(", r"\bexec\s*\(", r"os\.system", r"os\.popen",
                                       r"\bpickle\b", r"\bmarshal\b", r"__import__", r"verify\s*=\s*False", r"\bcompile\s*\("])
def test_el_codigo_no_usa_nada_peligroso(prohibido):
    for archivo in CODIGO:
        codigo = _lee(archivo)
        encontrado = [linea.strip() for linea in codigo.splitlines() if re.search(prohibido, linea) and "re.compile(" not in linea]
        assert not encontrado, f"{archivo.name}: {encontrado}"


def test_las_unicas_direcciones_de_internet_del_codigo_son_las_de_openrouter():
    permitidas = (
        "https://openrouter.ai/api/v1",  # la API de OpenRouter: /images y /key
        "http://127.0.0.1", "http://localhost", "http://{host}",  # este computador
    )
    # Nombres de formato XMP (identificadores dentro de los metadatos de las escenas): no se abren nunca.
    identificadores = {
        "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
    }
    vistas = set()
    for archivo in CODIGO:
        for direccion in re.findall(r"https?://[^\s\"'<>)\\]+", _lee(archivo)):
            vistas.add(direccion)
            if direccion in identificadores:
                assert archivo.name == "escenas.py"
                continue
            assert direccion.startswith(permitidas), f"{archivo.name}: {direccion}"
    assert "https://openrouter.ai/api/v1" in vistas


def test_solo_el_cliente_de_openrouter_habla_con_internet():
    redes = re.compile(r"^\s*(?:import|from)\s+(httpx|requests|urllib\.request|urllib3|aiohttp|http\.client|websockets|ftplib|smtplib)\b", re.M)
    usan_red = {archivo.name for archivo in CODIGO if redes.search(_lee(archivo))}
    assert usan_red == {"openrouter.py"}
    cliente = _lee(CARPETA / "estudio" / "openrouter.py")
    assert "follow_redirects=False" in cliente  # la clave no sigue redirecciones a otro servidor


def test_el_servidor_solo_escucha_en_este_computador():
    for archivo in CODIGO + sorted((CARPETA / "web").glob("*")) if (CARPETA / "web").is_dir() else CODIGO:
        texto = _lee(archivo)
        assert "0.0.0.0" not in texto, archivo.name
        for anfitrion in re.findall(r"host\s*=\s*[\"']([^\"']+)[\"']", texto):
            assert anfitrion == "127.0.0.1", f"{archivo.name}: host={anfitrion}"
    for palabra in ("ngrok", "cloudflared", "localtunnel", "--host"):
        assert not any(palabra in _lee(archivo) for archivo in CODIGO), palabra


def test_ningun_archivo_del_proyecto_lleva_una_clave():
    """Ni en el código, ni en las pruebas, ni en los documentos hay nada con forma de clave de OpenRouter."""
    clave = re.compile(rb"sk-or-v1-[0-9a-fA-F]{24,}")
    archivos = _archivos_del_proyecto()
    assert len(archivos) > 40
    for archivo in archivos:
        assert not clave.search(archivo.read_bytes()), f"hay algo con forma de clave en {archivo.relative_to(RAIZ)}"


def test_no_existe_ningun_env_de_ejemplo():
    nombres = {ruta.name for ruta in RAIZ.rglob(".env*") if not FUERA & set(ruta.relative_to(RAIZ).parts)}
    assert nombres <= {".env"}  # solo puede existir el que escribe la página de Ajustes


def test_la_clave_de_las_pruebas_se_inventa_al_ejecutar(clave_falsa):
    assert re.fullmatch(r"sk-or-v1-[0-9a-f]{64}", clave_falsa)
    for archivo in PRUEBAS:
        assert clave_falsa not in _lee(archivo)


def test_las_pruebas_no_tocan_los_archivos_reales_del_usuario():
    """Ninguna prueba nombra los archivos reales para escribirlos: todas piden la carpeta temporal."""
    for archivo in PRUEBAS:
        texto = _lee(archivo)
        for linea in texto.splitlines():
            if re.search(r"(RAIZ|CARPETA)\s*/\s*[\"'](\.env|ajustes\.json|gastos\.jsonl|salidas)[\"']", linea):
                assert "!=" in linea or archivo.name == "conftest.py" or "==" in linea, f"{archivo.name}: {linea.strip()}"
            assert not re.search(r"\.(write_text|write_bytes|unlink|touch)\(", linea) or "RAIZ /" not in linea, f"{archivo.name}: {linea.strip()}"


# --- Los vigilantes -----------------------------------------------------------------------------------------------------


def test_el_vigilante_nota_si_cambia_un_archivo_real(tmp_path, monkeypatch):
    """La huella que compara el vigilante cambia si alguien toca el .env, los ajustes, los gastos o las salidas."""
    raiz, carpeta = tmp_path / "herramientas-ia", tmp_path / "herramientas-ia" / "estudio-fotos"
    (carpeta / "salidas").mkdir(parents=True)
    monkeypatch.setattr(conftest, "RAIZ", raiz)
    monkeypatch.setattr(conftest, "CARPETA", carpeta)
    vacia = conftest._huella_de_los_archivos_reales()
    assert vacia == {".env": None, "ajustes.json": None, "gastos.jsonl": None, "logo_negocio.png": None, "salidas": []}

    cambios = {
        ".env": raiz / ".env",
        "ajustes.json": carpeta / "ajustes.json",
        "gastos.jsonl": carpeta / "gastos.jsonl",
        "salidas": carpeta / "salidas" / "sesion" / "foto.jpg",
    }
    for nombre, ruta in cambios.items():
        antes = conftest._huella_de_los_archivos_reales()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("x", encoding="utf-8")
        despues = conftest._huella_de_los_archivos_reales()
        assert antes[nombre] != despues[nombre], nombre


def test_el_vigilante_esta_puesto_para_todas_las_pruebas():
    texto = _lee(CARPETA / "pruebas" / "conftest.py")
    assert '@pytest.fixture(scope="session", autouse=True)\ndef archivos_reales_intactos' in texto
    assert '@pytest.fixture(scope="session", autouse=True)\ndef sin_internet' in texto


@pytest.mark.parametrize("direccion", ["https://openrouter.ai/api/v1/key", "https://example.com/", "http://192.168.1.1/"])
def test_desde_las_pruebas_no_se_puede_llamar_a_internet(direccion):
    with pytest.raises(AssertionError, match="intentó llamar a internet"):
        httpx.get(direccion, timeout=2)
    from estudio.openrouter import Cliente

    with pytest.raises(AssertionError, match="intentó llamar a internet"):
        Cliente("https://openrouter.ai/api/v1", lambda: "sk-or-v1-clave-inventada").probar()


def test_la_telemetria_de_fastapi_esta_apagada(config, monkeypatch):
    """Aunque el entorno pida enviar trazas a otro servidor, la herramienta no envía nada."""
    from estudio.servidor import crear_aplicacion

    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
    aplicacion = crear_aplicacion(config)
    try:
        for ajuste in ("tracing", "metrics", "logs", "operation_spans", "auto_configure"):
            assert aplicacion._telemetry[ajuste] is False, ajuste
        assert not aplicacion._native_telemetry.enabled()
        assert (aplicacion.docs_url, aplicacion.redoc_url, aplicacion.openapi_url) == (None, None, None)
    finally:
        aplicacion.state.estudio.cerrar()
