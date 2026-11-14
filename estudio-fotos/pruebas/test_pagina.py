"""Paso 14: la página. Comprobaciones sobre sus archivos (sin navegador): nada de internet, la firma y las tres zonas."""

from __future__ import annotations

import re

import pytest

from conftest import CARPETA, RAIZ

WEB = CARPETA / "web"
ENLACE_FIRMA = "https://marketingaios.com/?origen=herramienta-estudio-fotos"


def _lee(nombre: str) -> str:
    return (WEB / nombre).read_text(encoding="utf-8")


def _sin_comentarios(html: str) -> str:
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def test_la_pagina_esta_en_espanol_y_tiene_las_tres_zonas():
    html = _lee("index.html")
    assert '<html lang="es">' in html and '<meta charset="utf-8" />' in html
    botones = re.findall(r'<button type="button" class="zona-boton" data-zona="(\w+)"[^>]*>([^<]+)</button>', html)
    assert botones == [("fotos", "Fotos"), ("resultados", "Resultados"), ("ajustes", "Ajustes")]
    for zona in ("zona-fotos", "zona-resultados", "zona-ajustes"):
        assert f'id="{zona}"' in html
    assert "Arrastra aquí tus fotos" in html  # el estado vacío
    assert 'accept="image/jpeg,image/png,image/webp"' in html and " multiple" in html


def test_la_firma_de_ismagit_esta_en_el_pie_tal_como_en_estilo_firma():
    html = _lee("index.html")
    firma = re.search(r"<footer class=\"firma\">.*?</footer>", (RAIZ / "estilo" / "firma.html").read_text(encoding="utf-8"), re.S).group(0)
    compacta = lambda texto: " ".join(texto.split())  # la misma firma, sin mirar la sangría
    assert compacta(firma) in compacta(html)
    assert html.count("<footer") == 1 and compacta(html).endswith("</footer> </body> </html>")
    assert "Hecho con la guía de Ismagit" in firma and f'href="{ENLACE_FIRMA}"' in firma
    assert 'src="/marca/ismagit_logo.png"' in firma
    assert (RAIZ / "marca" / "ismagit_logo.png").is_file()


def test_la_pagina_no_carga_nada_de_internet():
    """Ni fuentes, ni librerías, ni iconos de fuera: la única dirección de internet es el enlace de la firma.

    Las fuentes son archivos de `estilo/fuentes/` (la lista blanca está en `test_diseno.py`).
    """
    comun = RAIZ / "estilo" / "estilo.css"
    archivos = sorted(p for p in WEB.rglob("*") if p.is_file())
    assert {p.name for p in archivos} >= {"index.html", "app.css", "app.js"}
    for archivo in archivos + [comun]:
        assert archivo.suffix in {".html", ".css", ".js"}, f"archivo inesperado en la página: {archivo.name}"
        texto = archivo.read_text(encoding="utf-8")
        direcciones = re.findall(r"(?:https?:)?//[A-Za-z0-9][^\s\"'<>)]*", re.sub(r"\s//\s.*", "", texto))
        direcciones = [d for d in direcciones if not d.startswith("//")] + [d for d in direcciones if d.startswith("//") and "." in d.split("/")[2]]
        assert set(direcciones) <= {ENLACE_FIRMA}, f"{archivo.name} nombra {direcciones}"
        assert "@import" not in texto
        if archivo != comun:  # las fuentes solo se declaran en la hoja común
            assert "@font-face" not in texto and "url(" not in texto, archivo.name

    html = _sin_comentarios(_lee("index.html"))
    cargas = re.findall(r'(?:src|href)="([^"]+)"', html)
    assert all(c.startswith(("/web/", "/estilo/", "/marca/")) or c == ENLACE_FIRMA for c in cargas), cargas
    # Lo único que carga la hoja común son las cuatro fuentes Geist de su carpeta: archivos que existen, sin dirección.
    cargas_css = re.findall(r"url\(([^)]*)\)", comun.read_text(encoding="utf-8"))
    assert len(cargas_css) == 4
    for carga in cargas_css:
        assert re.fullmatch(r'"fuentes/[a-z-]+\.woff2"', carga), carga
        assert (comun.parent / carga.strip('"')).is_file()


def test_la_pagina_de_inicio_tampoco_carga_nada_de_internet():
    """`inicio/index.html` se abre como archivo: solo carga archivos de la carpeta; lo demás son enlaces."""
    inicio = RAIZ / "inicio"
    archivos = sorted(p for p in inicio.rglob("*") if p.is_file())
    assert {p.name for p in archivos} >= {"index.html", "inicio.css"}
    for archivo in archivos:
        assert archivo.suffix in {".html", ".css"}, f"archivo inesperado en inicio/: {archivo.name}"
        texto = archivo.read_text(encoding="utf-8")
        assert "@import" not in texto and "@font-face" not in texto and "url(" not in texto, archivo.name
        assert "fonts.g" not in texto.lower()  # las fuentes llegan de ../estilo/estilo.css, que las tiene en su carpeta

    html = _sin_comentarios((inicio / "index.html").read_text(encoding="utf-8"))
    assert "<script" not in html and "<style" not in html and " style=" not in html and "<iframe" not in html
    assert not re.search(r"\son[a-z]+\s*=", html) and "javascript:" not in html
    # Lo que la página carga (hojas de estilo e imágenes): rutas relativas a archivos que existen dentro de la carpeta.
    cargas = re.findall(r'<link\b[^>]*\bhref="([^"]+)"', html) + re.findall(r'\bsrc="([^"]+)"', html)
    assert len(cargas) >= 3, cargas
    for carga in cargas:
        assert "//" not in carga and ":" not in carga and not carga.startswith("/"), carga
        destino = (inicio / carga).resolve()
        assert destino.is_file() and RAIZ.resolve() in destino.parents, carga
    # Lo demás son enlaces que el usuario pulsa: las herramientas de este computador y la firma.
    enlaces = re.findall(r'<a\b[^>]*\bhref="([^"]+)"', html)
    assert enlaces and all(re.fullmatch(r"http://127\.0\.0\.1:\d{4,5}", e) or e == ENLACE_FIRMA for e in enlaces), enlaces
    direcciones = set(re.findall(r"(?:https?:)?//[A-Za-z0-9][^\s\"'<>)]*", html))
    assert direcciones <= {ENLACE_FIRMA} | {e for e in enlaces if e.startswith("http://127.0.0.1:")}, direcciones


def test_la_pagina_cumple_su_politica_de_contenido():
    """La política CSP solo deja pasar archivos propios: el HTML no lleva código ni estilos escritos dentro."""
    html = _sin_comentarios(_lee("index.html"))
    assert re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.S) == [""]  # un solo script, y en su archivo
    assert '<script src="/web/app.js" defer></script>' in html
    assert "<style" not in html and " style=" not in html
    assert not re.search(r"\son[a-z]+\s*=", html)  # ni onclick ni parecidos
    assert "javascript:" not in html


def test_el_codigo_de_la_pagina_escribe_los_datos_como_texto():
    """Los nombres de archivo, la escena que escribe el usuario y los mensajes nunca se insertan como HTML."""
    js = _lee("app.js")
    for prohibido in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                      "createContextualFragment", "srcdoc", "DOMParser"):
        assert prohibido not in js, prohibido
    assert not re.search(r"set(Timeout|Interval)\(\s*[\"'`]", js)
    assert "textContent" in js and '"use strict"' in js
    # Solo se habla con el propio servidor: todas las peticiones van a rutas que empiezan por /api/.
    assert "http" not in re.sub(r"//.*|/\*.*?\*/", "", js, flags=re.S).replace("history", "")
    for ruta in re.findall(r'pedir\(\s*"[A-Z]+",\s*[`"]([^`"]+)', js):
        assert ruta.startswith("/api/"), ruta
    assert "localStorage" not in js and "sessionStorage" not in js and "document.cookie" not in js


def test_el_enlace_de_la_firma_no_cuenta_de_donde_viene():
    html = _lee("index.html")
    enlace = re.search(r"<a [^>]*marketingaios[^>]*>", html).group(0)
    assert 'rel="noopener"' in enlace and 'target="_blank"' in enlace


def test_el_servidor_sirve_la_pagina_y_sus_archivos(servidor):
    pagina = servidor.cliente.get("/")
    assert pagina.status_code == 200 and pagina.headers["content-type"] == "text/html; charset=utf-8"
    assert "<h1>Estudio de fotos</h1>" in pagina.text and "Hecho con la guía de Ismagit" in pagina.text
    assert "<title>Estudio de fotos de producto</title>" in pagina.text
    assert pagina.headers["cache-control"] == "no-store" and "default-src 'self'" in pagina.headers["content-security-policy"]
    assert pagina.headers["referrer-policy"] == "no-referrer"  # el enlace de la firma no lleva la dirección local
    for ruta, tipo in (("/web/app.js", "javascript"), ("/web/app.css", "text/css"), ("/estilo/estilo.css", "text/css"), ("/marca/ismagit_logo.png", "image/png")):
        respuesta = servidor.cliente.get(ruta)
        assert respuesta.status_code == 200 and tipo in respuesta.headers["content-type"], ruta
    for carga in re.findall(r'(?:src|href)="(/[^"]+)"', pagina.text):
        assert servidor.cliente.get(carga).status_code == 200, carga


@pytest.mark.parametrize("identificador", [
    "soltar", "elegir-fotos", "subiendo", "avisos-subida", "chip-modelo", "nota-modelo", "estado-modelo", "texto-modelo",
    "reintentar-modelo", "avance-recorte", "barra-recorte", "texto-recorte", "tarjeta-fotos", "lista-fotos",
    "empezar-de-nuevo", "aviso-puerto", "sin-respuesta",
])
def test_lo_que_usa_el_codigo_existe_en_la_pagina(identificador):
    assert f'id="{identificador}"' in _lee("index.html")
    assert f'"{identificador}"' in _lee("app.js")


def test_ajustes_solo_tiene_la_clave_la_calidad_del_recorte_y_las_escenas():
    """Versión 1.1: sin marca del negocio. Ni nombre, ni colores, ni logo; y la página ya no cambia de colores."""
    html, js = _lee("index.html"), _lee("app.js")
    ajustes = html[html.index('id="zona-ajustes"') : html.index("</main>")]
    assert re.findall(r"<h2[^>]*>([^<]+)</h2>", ajustes) == ["Ajustes", "Clave de OpenRouter", "Calidad del recorte", "Escenas con IA"]
    campos = set(re.findall(r'<(?:input|select|textarea)[^>]*\bid="([a-z0-9-]+)"', ajustes))
    assert campos == {"clave", "modelo-escenas", "tope-sesion"}
    assert set(re.findall(r'<input[^>]*\bname="([a-z]+)"', ajustes)) == {"calidad"}
    assert 'type="file"' not in ajustes and 'type="color"' not in ajustes  # ni logo que subir ni colores que elegir
    for resto in ("negocio", "logo", "Marca del negocio", "color_principal", "color_acento"):
        assert resto not in ajustes, resto
        assert resto not in js, resto
    # El único selector de color de la página es el del fondo liso de las escenas.
    assert re.findall(r'<input[^>]*type="color"[^>]*>', html) == ['<input type="color" id="color-escena" value="#d9d9d9" />']
    # Nada de lo que llega del servidor cambia los colores ni el título de la página.
    assert "documentElement.style" not in js and "--color" not in js and "document.title" not in js
    assert re.findall(r'setProperty\("(--[a-z-]+)"', js) == ["--corte"]  # solo la línea del antes y el después


def test_cada_identificador_que_pide_el_codigo_esta_en_la_pagina():
    html, js = _lee("index.html"), _lee("app.js")
    pedidos = set(re.findall(r'\$\("([a-z0-9-]+)"\)', js)) | set(re.findall(r'(?:caja|barra|texto|errores): "([a-z0-9-]+)"', js))
    faltan = sorted(i for i in pedidos if f'id="{i}"' not in html)
    assert not faltan, f"el código pide elementos que la página no tiene: {faltan}"
