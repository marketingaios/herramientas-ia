"""Versión 1.1 · el diseño de Ismagit (ficha, punto 4.7). Comprobaciones sobre los archivos, sin navegador.

Lo que calcula el navegador (colores ya aplicados, fuentes cargadas, foco, pantalla estrecha) lo mira el recorrido de
diseño de `test_e2e.py`.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from conftest import CARPETA, RAIZ

ESTILO = RAIZ / "estilo" / "estilo.css"
FUENTES = RAIZ / "estilo" / "fuentes"
WEB = CARPETA / "web"
INICIO = RAIZ / "inicio"

# La tabla del punto 4.7 de la ficha, tal cual.
VARIABLES = {
    "--bg": "#0B0C0D",
    "--card": "#111315",
    "--card2": "#15171A",
    "--texto": "#F2F2F0",
    "--texto-lectura": "#C5C7C5",
    "--gris": "#8B8D8F",
    "--linea": "rgba(255,255,255,.10)",
    "--acento": "#AFF320",
    "--acento-oscuro": "#0A0B0C",
    "--error": "#F07470",
    "--aviso": "#D8A35D",
}
ARCHIVOS_DE_FUENTES = ("geist-latin.woff2", "geist-latin-ext.woff2", "geist-mono-latin.woff2", "geist-mono-latin-ext.woff2")
CUADROS = "conic-gradient(#d5dae1 25%, #ffffff 0 50%, #d5dae1 0 75%, #ffffff 0) 0 0 / 20px 20px"  # cuadros claros


def _lee(ruta) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _reglas(css: str) -> list[tuple[list[str], dict[str, str]]]:
    """Las reglas de una hoja de estilo: (selectores, {propiedad: valor}). Las de dentro de un `@media`, también."""
    reglas = []
    for selectores, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", _sin_comentarios(css)):
        propiedades = {}
        for linea in cuerpo.split(";"):
            if ":" in linea:
                nombre, valor = linea.split(":", 1)
                propiedades[nombre.strip()] = " ".join(valor.split())
        reglas.append(([s.strip() for s in selectores.split(",")], propiedades))
    return reglas


def _regla(css: str, selector: str) -> dict[str, str]:
    """Todo lo que la hoja dice de un selector (si aparece en varias reglas, se suman en orden)."""
    propiedades: dict[str, str] = {}
    for selectores, cuerpo in _reglas(css):
        if selector in selectores:
            propiedades.update(cuerpo)
    assert propiedades, f"la hoja de estilo no tiene ninguna regla para {selector}"
    return propiedades


def _variables() -> dict[str, str]:
    return {nombre: valor for nombre, valor in _regla(_lee(ESTILO), ":root").items() if nombre.startswith("--")}


def _hojas() -> dict[str, str]:
    return {ruta.name: _lee(ruta) for ruta in (ESTILO, WEB / "app.css", INICIO / "inicio.css")}


# --- Las variables ------------------------------------------------------------------------------------------------


def test_las_variables_de_color_son_las_de_la_ficha():
    variables = _variables()
    compacto = lambda valor: valor.replace(" ", "").lower()
    for nombre, valor in VARIABLES.items():
        assert compacto(variables[nombre]) == compacto(valor), nombre
    # Además de los 11 colores de la ficha solo hay medidas y fuentes: ningún otro color con nombre propio.
    assert set(variables) - set(VARIABLES) == {"--radio", "--radio-chico", "--radio-boton", "--fuente", "--fuente-mono"}
    assert (variables["--radio"], variables["--radio-boton"]) == ("12px", "999px")
    assert _lee(ESTILO).count(":root") == 1  # las variables se definen una sola vez, y en la hoja común


def test_cada_variable_que_se_usa_existe_y_las_once_de_la_ficha_se_usan():
    """Una variable mal escrita (o una de la versión 1) dejaría un color sin pintar sin que nada avisara."""
    definidas = set(_variables()) | {"--corte"}  # `--corte` es la línea del antes y el después de cada foto
    usadas = set()
    for nombre, css in _hojas().items():
        de_esta = set(re.findall(r"var\((--[a-z0-9-]+)", css))
        assert de_esta <= definidas, f"{nombre} usa variables que no existen: {sorted(de_esta - definidas)}"
        usadas |= de_esta
        if nombre != "estilo.css":  # las demás hojas no definen ni cambian ninguna
            assert re.findall(r"(--[a-z0-9-]+)\s*:", _sin_comentarios(css)) in ([], ["--corte"]), nombre
    assert set(VARIABLES) <= usadas, f"variables de la ficha sin usar: {sorted(set(VARIABLES) - usadas)}"
    # Ni la página ni su código definen o cambian colores por su cuenta.
    for archivo in (WEB / "index.html", WEB / "app.js", INICIO / "index.html", RAIZ / "estilo" / "firma.html"):
        texto = _lee(archivo)
        assert " style=" not in texto and "<style" not in texto, archivo.name
        # Una variable de CSS en el código o en la página va entre comillas o dentro de `var(`.
        assert set(re.findall(r"""[("'`](--[a-z][a-z0-9-]+)""", texto)) <= {"--corte"}, archivo.name


def test_los_colores_de_las_hojas_salen_de_las_variables():
    """Fuera de `:root`, los únicos colores escritos a mano son los del fondo real de las fotos (blanco y cuadros
    claros) y lo que va pintado encima de una foto (la línea del antes y el después y sus rótulos)."""
    permitidos = {"#ffffff", "#d5dae1"}
    for nombre, css in _hojas().items():
        for selectores, cuerpo in _reglas(css):
            if selectores == [":root"]:
                continue
            for propiedad, valor in cuerpo.items():
                for color in re.findall(r"#[0-9a-fA-F]{3,8}\b", valor):
                    assert color.lower() in permitidos, f"{nombre}: {selectores} {propiedad}: {valor}"
                    assert nombre == "app.css", f"{nombre}: {selectores} {propiedad}: {valor}"
                for color in re.findall(r"rgba?\([^)]*\)", valor):
                    assert color.startswith("rgba(10, 11, 12, "), f"{nombre}: {selectores} {propiedad}: {valor}"


# --- Las fuentes --------------------------------------------------------------------------------------------------


def test_las_fuentes_geist_estan_en_estilo_fuentes_con_su_licencia():
    for nombre in ARCHIVOS_DE_FUENTES:
        copia = FUENTES / nombre
        assert copia.is_file() and not copia.is_symlink(), nombre
        assert copia.read_bytes()[:4] == b"wOF2"
        assert copia.read_bytes() == (RAIZ / "marca" / "fuentes" / nombre).read_bytes(), f"{nombre} no es la de la guía"
    licencia = _lee(FUENTES / "OFL.txt")
    assert "SIL OPEN FONT LICENSE" in licencia and "Geist" in licencia
    assert licencia == _lee(RAIZ / "marca" / "fuentes" / "OFL.txt")
    assert {ruta.name for ruta in FUENTES.iterdir()} == {*ARCHIVOS_DE_FUENTES, "OFL.txt"}  # y nada más


def test_las_fuentes_solo_se_cargan_de_estilo_fuentes():
    """Nada de Google Fonts ni de otra fuente de internet. Lista blanca: los `@font-face` están solo en la hoja común y
    cada uno carga un archivo de `estilo/fuentes/`, con una ruta relativa que no sale de ahí."""
    css = _sin_comentarios(_lee(ESTILO))
    caras = [cuerpo for selectores, cuerpo in _reglas(css) if selectores == ["@font-face"]]
    assert Counter(cara["font-family"] for cara in caras) == {'"Geist"': 2, '"Geist Mono"': 2}
    usados = set()
    for cara in caras:
        assert set(cara) == {"font-family", "font-style", "font-weight", "font-display", "src", "unicode-range"}
        assert cara["font-weight"] == "100 900"  # variables: del 100 al 900
        origen = re.fullmatch(r'url\("fuentes/([a-z-]+\.woff2)"\) format\("woff2"\)', cara["src"])
        assert origen, cara["src"]
        assert (FUENTES / origen[1]).is_file()
        usados.add(origen[1])
        assert cara["unicode-range"].startswith("U+")
    assert usados == set(ARCHIVOS_DE_FUENTES)

    # Cada `url(` de la hoja común es una de esas cuatro: sin dirección, sin «..», sin datos incrustados.
    cargas = re.findall(r"url\(([^)]*)\)", css)
    assert len(cargas) == 4
    for carga in cargas:
        assert re.fullmatch(r'"fuentes/[a-z-]+\.woff2"', carga), carga
        assert "//" not in carga and ":" not in carga and ".." not in carga and "data" not in carga
    assert "@import" not in css and "local(" not in css and "image-set(" not in css

    # En ningún otro archivo de las páginas hay fuentes ni cargas: ni `@font-face`, ni `url(`, ni `@import`.
    otros = [ruta for carpeta in (WEB, INICIO, RAIZ / "estilo") for ruta in carpeta.rglob("*")
             if ruta.is_file() and ruta.suffix in {".css", ".html", ".js"} and ruta != ESTILO]
    assert {ruta.name for ruta in otros} >= {"app.css", "app.js", "index.html", "inicio.css", "firma.html"}
    for ruta in otros:
        texto = _lee(ruta).lower()
        for prohibido in ("@font-face", "url(", "@import", "fontface", "fonts.googleapis", "fonts.gstatic", ".woff", ".ttf", ".otf"):
            assert prohibido not in texto, f"{ruta.name}: {prohibido}"
    assert "fonts.googleapis" not in css.lower() and "fonts.gstatic" not in css.lower()


def test_geist_para_todo_y_geist_mono_para_cifras_medidas_y_nombres_de_archivo():
    variables = _variables()
    assert variables["--fuente"].startswith('"Geist", ') and variables["--fuente-mono"].startswith('"Geist Mono", ')
    estilo, app = _lee(ESTILO), _lee(WEB / "app.css")
    assert _regla(estilo, "body")["font-family"] == "var(--fuente)"
    assert _regla(estilo, "code")["font-family"] == "var(--fuente-mono)"
    # Los campos y los botones heredan la fuente de la página (los navegadores no lo hacen solos).
    assert _regla(estilo, ".boton")["font"] == "inherit" and _regla(estilo, "select")["font"] == "inherit"
    for selector in (".avance-texto", ".foto-nombre", ".foto-estado", ".plataforma-medida", ".resultado-archivo",
                     ".resultado-datos", ".confirmar strong", "#gasto-sesion", "#mascara-clave", "#texto-color-escena"):
        assert _regla(app, selector)["font-family"] == "var(--fuente-mono)", selector
    # Ninguna hoja nombra otra familia: todo sale de las dos variables.
    for nombre, css in _hojas().items():
        for selectores, cuerpo in _reglas(css):
            if selectores not in ([":root"], ["@font-face"]) and "font-family" in cuerpo:
                assert cuerpo["font-family"] in ("var(--fuente)", "var(--fuente-mono)"), f"{nombre}: {selectores}"


# --- Botones, tarjetas, campos y foco -------------------------------------------------------------------------------


def test_los_botones_las_tarjetas_y_los_campos_son_los_de_la_ficha():
    estilo = _lee(ESTILO)
    principal, boton = _regla(estilo, ".boton-principal"), _regla(estilo, ".boton")
    assert (principal["background"], principal["color"]) == ("var(--acento)", "var(--acento-oscuro)")
    assert boton["border-radius"] == "var(--radio-boton)"  # 999px
    assert (boton["background"], boton["border"]) == ("transparent", "1px solid var(--linea)")
    tarjeta = _regla(estilo, ".tarjeta")
    assert (tarjeta["background"], tarjeta["border"], tarjeta["border-radius"]) == ("var(--card)", "1px solid var(--linea)", "var(--radio)")
    for campo in ('input[type="text"]', 'input[type="password"]', 'input[type="number"]', "select", "textarea"):
        assert _regla(estilo, campo)["background"] == "var(--card2)", campo
    assert _regla(estilo, "body")["background"] == "var(--bg)" and _regla(estilo, "body")["color"] == "var(--texto)"
    assert _regla(estilo, ".barra > div")["background"] == "var(--acento)"  # trabajando: la barra en el acento
    assert _regla(estilo, ".nota-error")["color"] == "var(--error)" and _regla(estilo, ".nota-aviso")["color"] == "var(--aviso)"
    assert "box-shadow" not in tarjeta and "color-scheme: dark" in estilo  # un diseño oscuro y plano


def test_el_foco_del_teclado_se_ve():
    foco = _regla(_lee(ESTILO), ":focus-visible")
    assert (foco["outline"], foco["outline-offset"]) == ("2px solid var(--acento)", "2px")
    # Ninguna regla lo quita; y lo que se maneja con un control invisible (soltar fotos, el deslizador) lo enseña
    # en su caja.
    for nombre, css in _hojas().items():
        assert not re.search(r"outline(-width|-style)?\s*:\s*(none|0)\b", css), nombre
    app = _lee(WEB / "app.css")
    for selector in (".soltar:focus-within", ".comparador:focus-within"):
        assert _regla(app, selector)["outline"] == "2px solid var(--acento)", selector


def _luminancia(color: str) -> float:
    canales = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _contraste(texto: str, fondo: str) -> float:
    claro, oscuro = sorted((_luminancia(texto), _luminancia(fondo)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


@pytest.mark.parametrize(
    "texto, fondo",
    [
        ("--texto", "--bg"), ("--texto", "--card"), ("--texto", "--card2"),
        ("--texto-lectura", "--bg"), ("--texto-lectura", "--card"), ("--texto-lectura", "--card2"),
        ("--gris", "--bg"), ("--gris", "--card"), ("--gris", "--card2"),
        ("--acento-oscuro", "--acento"),  # el botón principal
        ("--acento", "--bg"), ("--acento", "--card"), ("--acento", "--card2"),  # lo activo y lo que salió bien
        ("--error", "--card"), ("--error", "--card2"),
        ("--aviso", "--card"), ("--aviso", "--card2"),
    ],
)
def test_el_texto_cumple_el_contraste_aa(texto, fondo):
    variables = _variables()
    assert _contraste(variables[texto], variables[fondo]) >= 4.5, (texto, fondo)


def test_cada_texto_de_color_va_sobre_un_fondo_comprobado():
    """Los textos de las hojas usan solo las parejas de arriba: el color de una variable de texto sobre `--bg`,
    `--card` o `--card2` (y `--acento-oscuro`, solo sobre el acento). Lo blanco va encima de una foto, sobre un
    rótulo casi negro."""
    de_texto = {"var(--texto)", "var(--texto-lectura)", "var(--gris)", "var(--acento)", "var(--acento-oscuro)",
                "var(--error)", "var(--aviso)", "inherit", "#ffffff"}
    de_fondo = {"var(--bg)", "var(--card)", "var(--card2)", "var(--acento)", "transparent", "none", "#ffffff", CUADROS}
    for nombre, css in _hojas().items():
        for selectores, cuerpo in _reglas(css):
            if "color" in cuerpo:
                assert cuerpo["color"] in de_texto, f"{nombre}: {selectores} color: {cuerpo['color']}"
            if cuerpo.get("color") == "var(--acento-oscuro)":
                assert cuerpo["background"] == "var(--acento)", selectores
            if cuerpo.get("color") == "#ffffff":
                assert cuerpo["background"].startswith("rgba(10, 11, 12, 0.7"), selectores
            fondo = cuerpo.get("background")
            if fondo and not fondo.startswith(("rgba(10, 11, 12, 0.7", "color-mix(in srgb, var(--acento) 8%, var(--card2))")):
                assert fondo in de_fondo, f"{nombre}: {selectores} background: {fondo}"
    # Las notas (avisos, errores, lo que salió bien) van sobre el fondo de los campos, con el texto del color de su estado.
    assert _regla(_lee(ESTILO), ".nota")["background"] == "var(--card2)"


# --- La firma ---------------------------------------------------------------------------------------------------------


def test_la_firma_lleva_el_logo_pequeno_de_ismagit_y_su_enlace():
    assert (RAIZ / "marca" / "ismagit_logo.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    firma = " ".join(_lee(RAIZ / "estilo" / "firma.html").split())
    assert '<img src="/marca/ismagit_logo.png" alt="Ismagit" height="18" />' in firma
    assert "<span>Hecho con la guía de Ismagit</span>" in firma
    assert 'href="https://marketingaios.com/?origen=herramienta-estudio-fotos"' in firma
    assert _regla(_lee(ESTILO), ".firma img")["height"] == "18px"
    # La misma firma, en el pie de las dos páginas (cada una con su ruta al logo).
    for pagina, logo in ((WEB / "index.html", "/marca/ismagit_logo.png"), (INICIO / "index.html", "../marca/ismagit_logo.png")):
        html = " ".join(_lee(pagina).split())
        pie = html[html.index('<footer class="firma">') :]
        assert f'<img src="{logo}" alt="Ismagit" height="18" /> <span>Hecho con la guía de Ismagit</span>' in pie, pagina
