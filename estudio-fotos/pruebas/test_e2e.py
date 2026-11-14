"""De punta a punta: la página en un navegador de verdad (Playwright con Chromium sin ventana).

El servidor se arranca como lo arranca el usuario (`python -m estudio`), en otro puerto, con `NO_ABRIR_NAVEGADOR=1`,
los datos en una carpeta temporal, el modelo real de recorte y OpenRouter simulado. Se pasan con:

    uv run --group pruebas pytest -m e2e

Los recorridos van en orden y comparten la misma página, como una sesión de uso.
"""

from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import ayudas
from conftest import RAIZ, fotos_de_muestra, lado_corto

pytestmark = pytest.mark.e2e

ENLACE_FIRMA = "https://marketingaios.com/?origen=herramienta-estudio-fotos"
CAPTURAS = os.environ.get("E2E_CAPTURAS", "")  # una carpeta donde dejar capturas de pantalla (opcional)
MUESTRAS = fotos_de_muestra()  # todas las fotos de muestras/, las que haya: ninguna cuenta depende de un número fijo
TOTAL = len(MUESTRAS)
FOTOS = [ruta.stem for ruta in MUESTRAS]


@pytest.fixture(scope="module")
def entorno(tmp_path_factory, clave_falsa):
    from simulador import Simulador
    from test_arranque import Proceso, _puerto_libre

    simulador = Simulador().arrancar()
    simulador.clave = clave_falsa
    datos = tmp_path_factory.mktemp("punta-a-punta")
    puerto = _puerto_libre()
    proceso = Proceso(datos, simulador, puerto, ESTUDIO_RECORTADOR=None)  # sin recorte simulado: el modelo real
    try:
        proceso.esperar_linea("Estudio de fotos abierto en ", 120)
        yield SimpleNamespace(
            url=f"http://127.0.0.1:{puerto}", puerto=puerto, simulador=simulador, clave=clave_falsa, datos=datos,
            proceso=proceso, peticiones=[], errores=[],
        )
    finally:
        proceso.parar()
        simulador.parar()


@pytest.fixture(scope="module")
def pagina(entorno):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch()  # sin ventana
        contexto = navegador.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900}, locale="es-ES")
        pagina = contexto.new_page()
        pagina.set_default_timeout(20_000)
        pagina.on("request", lambda peticion: entorno.peticiones.append(peticion.url))
        pagina.on("console", lambda mensaje: entorno.errores.append(mensaje.text) if mensaje.type == "error" else None)
        pagina.on("pageerror", lambda error: entorno.errores.append(str(error)))
        pagina.goto(entorno.url)
        yield pagina
        navegador.close()


def _captura(pagina, nombre: str) -> None:
    if CAPTURAS:
        Path(CAPTURAS).mkdir(parents=True, exist_ok=True)
        pagina.screenshot(path=str(Path(CAPTURAS) / f"{nombre}.png"), full_page=True)


def test_1_subir_todas_las_muestras_y_ver_un_recorte_por_foto(pagina, entorno):
    from playwright.sync_api import expect

    # La página vacía: el título, la zona para soltar y la firma en el pie.
    expect(pagina.locator("h1")).to_have_text("Estudio de fotos de producto")
    expect(pagina.locator("#soltar")).to_contain_text("Arrastra aquí tus fotos")
    expect(pagina.locator("footer.firma")).to_contain_text("Hecho con la guía de Ismagit")
    expect(pagina.locator("footer.firma a")).to_have_attribute("href", ENLACE_FIRMA)
    assert pagina.locator("footer.firma img").evaluate("img => img.complete && img.naturalWidth > 0")
    expect(pagina.locator(".zona-boton")).to_have_text(["Fotos", "Resultados", "Ajustes"])
    expect(pagina.locator("#chip-modelo")).to_be_visible()  # qué modelo de recorte toca en este computador
    assert pagina.locator("#chip-modelo").inner_text() in ("Calidad máxima", "Modo rápido")
    _captura(pagina, "1-vacia")

    # Sube todas las fotos de muestras/ y espera la barra hasta el final («N de N»).
    pagina.set_input_files("#elegir-fotos", [str(ruta) for ruta in MUESTRAS])
    expect(pagina.locator("#lista-fotos .foto")).to_have_count(TOTAL)
    expect(pagina.locator("#avance-recorte")).to_be_visible()
    expect(pagina.locator("#texto-recorte")).to_contain_text(f" de {TOTAL}")  # la barra, mientras trabaja
    _captura(pagina, "1-recortando")
    expect(pagina.locator("#texto-recorte")).to_contain_text(f"{TOTAL} de {TOTAL} · listo", timeout=900_000)
    assert pagina.locator("#barra-recorte").evaluate("barra => barra.style.width") == "100%"
    pagina.wait_for_function(  # la barra llega hasta el final
        "() => { const b = document.querySelector('#barra-recorte'); return b.getBoundingClientRect().width >= b.parentElement.getBoundingClientRect().width - 1; }"
    )

    # Las fotos de menos de 1.000 px de lado corto se aceptan con su aviso; las demás, sin él.
    pequenas = [ruta for ruta in MUESTRAS if lado_corto(ruta) < 1000]
    expect(pagina.locator("#avisos-subida li")).to_have_count(len(pequenas))
    for indice, ruta in enumerate(pequenas):
        expect(pagina.locator("#avisos-subida li").nth(indice)).to_have_text(
            re.compile(rf"^{re.escape(ruta.name)}: .*mide {lado_corto(ruta)} px de lado corto: con 1\.000 o más se verá mejor")
        )

    # Se ve un recorte por foto: antes y después, con el deslizador, sobre el fondo de cuadros.
    tarjetas = pagina.locator("#lista-fotos .foto")
    pagina.wait_for_function(
        "() => [...document.querySelectorAll('#lista-fotos img')].every(img => img.hidden || (img.complete && img.naturalWidth > 0))"
    )
    nombres = []
    for indice in range(TOTAL):
        tarjeta = tarjetas.nth(indice)
        nombres.append(tarjeta.locator(".foto-nombre").inner_text())
        expect(tarjeta.locator("img.despues")).to_be_visible()
        expect(tarjeta.locator("img.antes")).to_be_visible()
        expect(tarjeta.locator(".foto-estado")).to_have_text(re.compile(r"^\d+×\d+ px · \d+(,\d)?\s?s$"))  # medida y tiempo
        expect(tarjeta.locator(".nota-error")).to_be_hidden()
        assert "conic-gradient" in tarjeta.locator(".comparador").evaluate("caja => getComputedStyle(caja).backgroundImage")
        # El después es un recorte de verdad: tiene producto (opaco) y fondo transparente.
        opacos, transparentes = tarjeta.locator("img.despues").evaluate(
            """img => {
                const lienzo = document.createElement('canvas');
                lienzo.width = img.naturalWidth; lienzo.height = img.naturalHeight;
                const dibujo = lienzo.getContext('2d');
                dibujo.drawImage(img, 0, 0);
                const datos = dibujo.getImageData(0, 0, lienzo.width, lienzo.height).data;
                let opacos = 0, transparentes = 0;
                for (let i = 3; i < datos.length; i += 4) { if (datos[i] > 250) opacos++; else if (datos[i] < 5) transparentes++; }
                return [opacos / (datos.length / 4), transparentes / (datos.length / 4)];
            }"""
        )
        assert 0.05 < opacos < 0.95 and transparentes > 0.05, (nombres[-1], opacos, transparentes)
    assert nombres == [ruta.name for ruta in MUESTRAS]

    # El deslizador mueve la línea entre el antes y el después.
    primera = tarjetas.first
    assert primera.locator(".comparador").evaluate("caja => getComputedStyle(caja).getPropertyValue('--corte').trim()") == "50%"
    primera.locator(".deslizador").evaluate("d => { d.value = '80'; d.dispatchEvent(new Event('input', {bubbles: true})); }")
    assert primera.locator(".comparador").evaluate("caja => getComputedStyle(caja).getPropertyValue('--corte').trim()") == "80%"
    _captura(pagina, "1-recortes")


def _descargar(pagina, boton) -> zipfile.ZipFile:
    """Pulsa un botón de descarga y abre el ZIP que baja el navegador."""
    with pagina.expect_download() as descarga:
        boton.click()
    ruta = descarga.value.path()
    assert descarga.value.suggested_filename.startswith("estudio-fotos_") and descarga.value.suggested_filename.endswith(".zip")
    return zipfile.ZipFile(ruta)


def test_2_medidas_para_tres_plataformas_y_descarga_del_zip(pagina, entorno):
    from playwright.sync_api import expect

    fotos = FOTOS

    # Elige Mercado Libre, Amazon e Instagram.
    expect(pagina.locator("#lista-plataformas .plataforma")).to_have_count(8)
    expect(pagina.locator("#resumen-medidas")).to_have_text(f"{TOTAL} fotos × 8 plataformas = {TOTAL * 8} archivos")
    pagina.click("#plataformas-ninguna")
    expect(pagina.locator("#generar-medidas")).to_be_disabled()
    for nombre in ("Mercado Libre", "Amazon", "Instagram (feed)"):
        pagina.locator("#lista-plataformas .plataforma", has=pagina.get_by_text(nombre, exact=True)).locator("input").check()
    expect(pagina.locator("#resumen-medidas")).to_have_text(f"{TOTAL} fotos × 3 plataformas = {TOTAL * 3} archivos")
    _captura(pagina, "2-plataformas")

    # Genera, con su barra de avance.
    pagina.click("#generar-medidas")
    expect(pagina.locator("#texto-medidas")).to_contain_text(f"{TOTAL * 3} de {TOTAL * 3} · listo", timeout=120_000)
    expect(pagina.locator("#medidas-listas")).to_contain_text(f"Listo: {TOTAL * 3} archivos creados")
    expect(pagina.locator("#errores-medidas")).to_be_hidden()

    # Resultados: una cuadrícula por foto, con el recorte y las tres medidas.
    pagina.click("#ver-resultados")
    expect(pagina.locator("#zona-resultados")).to_be_visible()
    expect(pagina.locator("#zona-fotos")).to_be_hidden()
    bloques = pagina.locator("#lista-resultados .resultado-foto")
    expect(bloques).to_have_count(TOTAL)
    for indice, foto in enumerate(fotos):
        bloque = bloques.nth(indice)
        expect(bloque.locator("h3")).to_have_text(MUESTRAS[indice].name)
        expect(bloque.locator(".resultado-titulo")).to_have_text(["Recorte", "Mercado Libre", "Amazon", "Instagram (feed)"])
        archivos = bloque.locator(".resultado-archivo").all_inner_texts()
        assert archivos[0] == f"{foto}_recorte.png"
        assert archivos[1] == f"{foto}_mercadolibre_1200x1200.jpg" and archivos[3] == f"{foto}_instagram_1080x1350.jpg"
        assert re.fullmatch(rf"{foto}_amazon_(\d+)x\1\.jpg", archivos[2])
        expect(bloque.locator(".resultado-datos").nth(1)).to_contain_text("1200×1200")
        expect(bloque.locator(".resultado-datos").nth(1)).to_contain_text("producto al 95 %")
    # Para Amazon la medida baja hasta la que no amplía el producto, con un mínimo de 1000×1000: solo un archivo que
    # se quedó en ese mínimo puede llevar el aviso de ampliación (y por encima del mínimo, ninguno).
    avisos = pagina.locator("#lista-resultados .nota-aviso").all_inner_texts()
    de_amazon = [a for a in avisos if "Amazon pide no agrandar las fotos pequeñas" in a]
    en_el_minimo = [a for a in pagina.locator("#lista-resultados .resultado-archivo").all_inner_texts() if a.endswith("_amazon_1000x1000.jpg")]
    assert len(de_amazon) <= len(en_el_minimo), avisos
    assert all(re.fullmatch(r"ampliada ×\d,\d+: Amazon pide no agrandar las fotos pequeñas", a) for a in de_amazon), de_amazon
    pagina.wait_for_function(
        "() => [...document.querySelectorAll('#lista-resultados img')].slice(0, 4).every(img => img.complete && img.naturalWidth > 0)"
    )
    _captura(pagina, "2-resultados")

    # Descarga el ZIP con todo y comprueba los archivos.
    with _descargar(pagina, pagina.get_by_role("link", name="Descargar todo (ZIP)")) as archivo_zip:
        assert archivo_zip.testzip() is None
        nombres = sorted(archivo_zip.namelist())
        filas = list(csv.DictReader(io.StringIO(archivo_zip.read("resumen.csv").decode("utf-8-sig"))))
        imagenes = {nombre: archivo_zip.read(nombre) for nombre in nombres if nombre != "resumen.csv"}

    assert len(nombres) == TOTAL * 4 + 1 and "resumen.csv" in nombres  # un recorte y tres medidas por foto, y el resumen
    assert sorted(n for n in nombres if n.startswith("recortes/")) == [f"recortes/{foto}_recorte.png" for foto in fotos]
    assert sorted(n for n in nombres if n.startswith("mercadolibre/")) == [f"mercadolibre/{foto}_mercadolibre_1200x1200.jpg" for foto in fotos]
    assert sorted(n for n in nombres if n.startswith("instagram/")) == [f"instagram/{foto}_instagram_1080x1350.jpg" for foto in fotos]
    assert len([n for n in nombres if n.startswith("amazon/")]) == TOTAL

    assert list(filas[0]) == ["archivo", "plataforma", "medida", "peso_kb", "porcentaje_producto", "avisos"]
    assert sum("Amazon pide no agrandar" in fila["avisos"] for fila in filas) == len(de_amazon)  # lo mismo que en la página
    assert len(filas) == TOTAL * 4 and {fila["archivo"] for fila in filas} == {nombre.split("/")[1] for nombre in imagenes}
    esperado = {"mercadolibre": (95.0, 10_000), "amazon": (85.0, None), "instagram": (80.0, None)}
    for nombre, datos in imagenes.items():
        carpeta, archivo = nombre.split("/")
        fila = next(fila for fila in filas if fila["archivo"] == archivo)
        with Image.open(io.BytesIO(datos)) as imagen:
            imagen.load()
            assert f"{imagen.width}x{imagen.height}" == fila["medida"]
            assert carpeta == "recortes" or archivo.endswith(f"_{carpeta}_{fila['medida']}.jpg")  # <foto>_<plataforma>_<ancho>x<alto>.jpg
            assert int(fila["peso_kb"]) == -(-len(datos) // 1000)
            if carpeta == "recortes":
                assert imagen.format == "PNG" and imagen.mode == "RGBA"
                continue
            assert imagen.format == "JPEG" and imagen.mode == "RGB" and imagen.info.get("icc_profile")
            # Fondo blanco puro en las cuatro esquinas y en todo el borde.
            ancho, alto = imagen.size
            for punto in ((0, 0), (ancho - 1, 0), (0, alto - 1), (ancho - 1, alto - 1), (ancho // 2, 0), (0, alto // 2)):
                assert imagen.getpixel(punto) == (255, 255, 255), (nombre, punto)
            porcentaje, peso_maximo_kb = esperado[carpeta]
            assert abs(float(fila["porcentaje_producto"].replace(",", ".")) - porcentaje) <= 1.0, (nombre, fila)
            if peso_maximo_kb:
                assert int(fila["peso_kb"]) <= peso_maximo_kb
            if carpeta == "amazon":
                assert ancho == alto and 1000 <= ancho <= 2000
                # Sin ampliar: por encima del mínimo nunca hay aviso; solo sale en el mínimo, si hubo que ampliar.
                if "Amazon pide no agrandar" in fila["avisos"]:
                    assert ancho == 1000, fila
            else:
                assert "Amazon" not in fila["avisos"]
            if archivo.startswith("bolsa_mesa"):
                # Una comprobación de más, si esa muestra está en la carpeta (una bolsa de papel oscuro, que se
                # distingue bien del blanco): medido en la propia foto, el producto ocupa lo que toca y está
                # centrado, con un margen de ±1 %. El porcentaje de todas las fotos ya se comprobó arriba.
                izquierda, arriba, derecha, abajo = ayudas.caja_no_blanca(imagen)
                ocupa = max((derecha - izquierda) / ancho, (abajo - arriba) / alto) * 100
                assert abs(ocupa - porcentaje) <= 1.0, (nombre, ocupa)
                assert abs((izquierda + derecha) / 2 - ancho / 2) <= ancho * 0.01
                assert abs((arriba + abajo) / 2 - alto / 2) <= alto * 0.01

    # Y una sola plataforma.
    with _descargar(pagina, pagina.get_by_role("link", name="Solo Amazon")) as archivo_zip:
        solo_amazon = sorted(archivo_zip.namelist())
    assert len(solo_amazon) == TOTAL + 1 and all(n.startswith("amazon/") or n == "resumen.csv" for n in solo_amazon)

    # La firma sigue en el pie también en esta zona.
    expect(pagina.locator("footer.firma")).to_be_visible()
    pagina.click(".zona-boton[data-zona='fotos']")
    expect(pagina.locator("#zona-fotos")).to_be_visible()


def test_3_ajustes_la_clave_se_ve_enmascarada_y_probar_dice_conexion_correcta(pagina, entorno):
    import json

    from playwright.sync_api import expect

    clave = entorno.clave
    pagina.click(".zona-boton[data-zona='ajustes']")
    expect(pagina.locator("#zona-ajustes")).to_be_visible()
    expect(pagina.locator("#clave-guardada")).to_be_hidden()
    expect(pagina.locator("#clave")).to_have_attribute("type", "password")  # un campo de tipo contraseña

    # Guarda una clave falsa: después se ve «••••» y los 4 últimos caracteres, nunca entera.
    pagina.fill("#clave", clave)
    pagina.click("#guardar-clave")
    expect(pagina.locator("#mascara-clave")).to_have_text("••••" + clave[-4:])
    expect(pagina.locator("#clave")).to_have_value("")
    assert clave not in pagina.content() and clave[:20] not in pagina.content()
    assert clave not in pagina.evaluate("() => JSON.stringify([...document.querySelectorAll('input')].map(i => i.value))")

    # Probar (con OpenRouter simulado).
    pagina.click("#probar-clave")
    expect(pagina.locator("#resultado-clave")).to_have_text("Conexión correcta · límite 2,00 $ · usado 0,12 $")
    assert [(p["metodo"], p["ruta"], p["autorizada"]) for p in entorno.simulador.peticiones] == [("GET", "/api/v1/key", True)]
    _captura(pagina, "3-ajustes-clave")

    # La clave quedó en el archivo de claves de la carpeta temporal (solo su línea) y no en los ajustes.
    assert (entorno.datos / ".env").read_text(encoding="utf-8") == f"OPENROUTER_API_KEY={clave}\n"

    # La marca del negocio: nombre, colores y logo. La página usa esos colores.
    pagina.fill("#negocio-nombre", "Café 2600")
    for campo, color in (("#negocio-color-principal", "#1f3b2d"), ("#negocio-color-acento", "#c8a04b")):
        pagina.locator(campo).evaluate(
            "(campo, color) => { campo.value = color; campo.dispatchEvent(new Event('input', {bubbles: true})); }", color
        )
    pagina.set_input_files("#elegir-logo", str(RAIZ / "marca" / "cafe2600_logo.png"))
    expect(pagina.locator("#vista-logo")).to_be_visible()
    pagina.check("input[name='calidad'][value='maxima']")
    pagina.select_option("#modelo-escenas", "google/gemini-nano-banana-2.1")
    pagina.fill("#tope-sesion", "2")
    pagina.click("#guardar-ajustes")
    expect(pagina.locator("#ajustes-guardados")).to_be_visible()
    expect(pagina.locator("#nombre-negocio")).to_have_text("Café 2600")
    expect(pagina.locator("#logo-negocio")).to_be_visible()
    expect(pagina.locator("#gasto-sesion")).to_have_text("Gastado en esta sesión: 0,00 $ de 2,00 $ (quedan 2,00 $).")
    variable = "(nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim()"
    assert pagina.evaluate(variable, "--color-principal") == "#1F3B2D"
    assert pagina.evaluate(variable, "--color-acento") == "#C8A04B"
    assert pagina.evaluate("() => getComputedStyle(document.querySelector('.cabecera')).backgroundColor") == "rgb(31, 59, 45)"
    expect(pagina).to_have_title("Estudio de fotos · Café 2600")
    _captura(pagina, "3-ajustes-marca")

    guardado = json.loads((entorno.datos / "estudio-fotos" / "ajustes.json").read_text(encoding="utf-8"))
    assert guardado == {
        "negocio": {"nombre": "Café 2600", "color_principal": "#1F3B2D", "color_acento": "#C8A04B"},
        "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-nano-banana-2.1", "tope_sesion_usd": 2.0,
    }

    # Al recargar la página, todo sigue ahí (y la clave sigue enmascarada).
    pagina.reload()
    expect(pagina.locator("#zona-ajustes")).to_be_visible()  # recuerda la zona
    expect(pagina.locator("#mascara-clave")).to_have_text("••••" + clave[-4:])
    expect(pagina.locator("#negocio-nombre")).to_have_value("Café 2600")
    expect(pagina.locator("#tope-sesion")).to_have_value("2")
    expect(pagina.locator("input[name='calidad'][value='maxima']")).to_be_checked()
    assert clave not in pagina.content()
    expect(pagina.locator("footer.firma")).to_be_visible()

    # Las fotos y sus resultados siguen en la sesión.
    pagina.click(".zona-boton[data-zona='fotos']")
    expect(pagina.locator("#lista-fotos .foto")).to_have_count(TOTAL)


def test_4_dos_escenas_con_ia_ve_el_costo_antes_confirma_y_ve_el_costo_real(pagina, entorno):
    import json

    from playwright.sync_api import expect

    from estudio import escenas

    simulador = entorno.simulador
    simulador.costo = 0.05  # el costo real de cada imagen: distinto del de partida (0,04 $), para ver que se muestra
    gastos = entorno.datos / "estudio-fotos" / "gastos.jsonl"
    fotos = FOTOS
    antes = len(simulador.peticiones)

    # La tarjeta de escenas, con su marca. Se dejan marcadas 2 fotos: una escena por foto.
    pagina.click(".zona-boton[data-zona='fotos']")
    expect(pagina.locator("#tarjeta-escenas")).to_be_visible()
    expect(pagina.locator("#marca-escenas")).to_have_text("Para redes y fotos secundarias")
    expect(pagina.locator("#nota-escenas")).to_have_text("Mercado Libre y Amazon piden fondo blanco en la foto principal.")
    expect(pagina.locator("#escenas-sin-clave")).to_be_hidden()  # la clave se guardó en el recorrido 3
    expect(pagina.locator("#escena option")).to_have_text([
        "Mesa de madera clara con luz de mañana", "Cocina moderna, encimera de piedra",
        "Fondo liso de un color", "Exterior con luz natural suave", "Estudio con sombra suave",
        "Escribir la mía…",
    ])
    expect(pagina.locator("#formato-escena option")).to_have_text(["1:1", "4:5", "16:9"])
    expect(pagina.locator("#resumen-escenas")).to_contain_text(f"{TOTAL} fotos marcadas = {TOTAL} escenas")
    for indice in range(2, TOTAL):  # se quedan marcadas las dos primeras
        pagina.locator("#lista-fotos .foto").nth(indice).locator(".foto-usar input").uncheck()
    expect(pagina.locator("#resumen-escenas")).to_have_text("2 fotos marcadas = 2 escenas · modelo Nano Banana 2.1 (recomendado)")
    expect(pagina.locator("#campo-color-escena")).to_be_hidden()  # con la primera escena no hay color que elegir
    pagina.select_option("#escena", "propia")
    expect(pagina.locator("#campo-escena-propia")).to_be_visible()  # el campo para escribir la tuya
    expect(pagina.locator("#campo-color-escena")).to_be_hidden()
    pagina.select_option("#escena", "mesa-madera")
    expect(pagina.locator("#campo-escena-propia")).to_be_hidden()
    expect(pagina.locator("#campo-color-escena")).to_be_hidden()

    # El selector de color solo se ve con «Fondo liso de un color»; por defecto, gris claro.
    pagina.select_option("#escena", "fondo-liso")
    expect(pagina.locator("#campo-color-escena")).to_be_visible()
    expect(pagina.locator("#campo-escena-propia")).to_be_hidden()
    expect(pagina.locator("#color-escena")).to_have_attribute("type", "color")
    expect(pagina.locator("#color-escena")).to_have_value("#d9d9d9")
    expect(pagina.locator("#texto-color-escena")).to_have_text("#D9D9D9")
    pagina.fill("#color-escena", "#3366cc")
    expect(pagina.locator("#texto-color-escena")).to_have_text("#3366CC")
    pagina.select_option("#formato-escena", "4:5")

    # Antes de gastar: el costo estimado, y hay que confirmar. Todavía no se ha pedido ni anotado nada.
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()
    pagina.click("#ver-costo")
    expect(pagina.locator("#texto-estimacion")).to_have_text("2 escenas · costo estimado 0,08 $ · ¿Generar?")
    expect(pagina.locator("#generar-escenas")).to_be_visible()
    _captura(pagina, "4-estimacion")
    assert len(simulador.peticiones) == antes and not gastos.exists()

    # Si cambia lo que se va a pedir, la confirmación desaparece: hay que volver a ver el costo.
    pagina.select_option("#formato-escena", "1:1")
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()
    pagina.select_option("#formato-escena", "4:5")
    pagina.click("#ver-costo")
    expect(pagina.locator("#texto-estimacion")).to_have_text("2 escenas · costo estimado 0,08 $ · ¿Generar?")
    pagina.fill("#color-escena", "#112233")  # también si cambia el color
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()
    pagina.fill("#color-escena", "#3366cc")
    pagina.click("#ver-costo")
    expect(pagina.locator("#texto-estimacion")).to_have_text("2 escenas · costo estimado 0,08 $ · ¿Generar?")
    _captura(pagina, "4-fondo-liso-color")
    assert len(simulador.peticiones) == antes

    # Confirma: la barra de avance y, al terminar, el costo real.
    pagina.click("#generar-escenas")
    expect(pagina.locator("#avance-escenas")).to_be_visible()
    expect(pagina.locator("#texto-escenas")).to_contain_text("2 de 2 · listo", timeout=60_000)
    expect(pagina.locator("#texto-escenas-listas")).to_have_text(
        "Listo: 2 escenas · costo real 0,10 $ (estimado 0,08 $). En esta sesión llevas 0,10 $ de 2,00 $."
    )
    expect(pagina.locator("#errores-escenas")).to_be_hidden()
    expect(pagina.locator("#escenas-detenidas")).to_be_hidden()
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()
    _captura(pagina, "4-escenas-listas")

    # A OpenRouter (simulado) se le preguntó cuánto queda en la clave y se le pidieron exactamente 2 imágenes.
    nuevas = simulador.peticiones[antes:]
    assert [(p["metodo"], p["ruta"], p["autorizada"]) for p in nuevas] == [
        ("GET", "/api/v1/key", True), ("POST", "/api/v1/images", True), ("POST", "/api/v1/images", True),
    ]
    assert simulador.violaciones == []
    for peticion in nuevas[1:]:
        cuerpo = peticion["cuerpo"]
        assert (cuerpo["model"], cuerpo["aspect_ratio"], cuerpo["resolution"]) == ("google/gemini-nano-banana-2.1", "4:5", "1K")
        assert "Usa exactamente ese producto" in cuerpo["prompt"]
        assert "fondo liso" in cuerpo["prompt"] and "el color #3366CC" in cuerpo["prompt"]  # el color elegido
        assert "#112233" not in cuerpo["prompt"]

    # Cada gasto quedó anotado (en la carpeta temporal), sin la clave.
    texto_gastos = gastos.read_text(encoding="utf-8")
    lineas = [json.loads(linea) for linea in texto_gastos.splitlines()]
    assert len(lineas) == 2 and entorno.clave not in texto_gastos and "sk-or-" not in texto_gastos
    assert "#3366cc" not in texto_gastos.lower()  # el color solo va en el texto de la petición
    for linea in lineas:
        assert set(linea) == {"ts", "modelo", "imagenes", "costo_estimado_usd", "costo_usd"}
        assert (linea["modelo"], linea["imagenes"], linea["costo_estimado_usd"], linea["costo_usd"]) == (
            "google/gemini-nano-banana-2.1", 1, 0.04, 0.05)
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", linea["ts"])

    # Resultados: las 2 escenas, cada una en la cuadrícula de su foto y marcadas «Para redes y fotos secundarias».
    pagina.click("#ver-escenas")
    expect(pagina.locator("#zona-resultados")).to_be_visible()
    bloques = pagina.locator("#lista-resultados .resultado-foto")
    expect(pagina.locator("#lista-resultados .resultado .chip")).to_have_count(2)
    archivos_escena = []
    for indice, foto in enumerate(fotos):
        bloque = bloques.nth(indice)
        titulos = bloque.locator(".resultado-titulo").all_inner_texts()
        if indice >= 2:
            assert titulos == ["Recorte", "Mercado Libre", "Amazon", "Instagram (feed)"]
            continue
        assert titulos == ["Recorte", "Mercado Libre", "Amazon", "Instagram (feed)", "Escena: Fondo liso de un color (#3366CC)"]
        escena = bloque.locator(".resultado").last
        expect(escena.locator(".chip")).to_have_text("Para redes y fotos secundarias")
        archivo = escena.locator(".resultado-archivo").inner_text()
        medida = re.fullmatch(rf"{foto}_escena_fondo-liso_(\d+)x(\d+)\.jpg", archivo)
        assert medida, archivo
        ancho, alto = int(medida[1]), int(medida[2])
        assert ancho * 5 == alto * 4 or abs(ancho / alto - 4 / 5) < 0.002, archivo  # el formato pedido: 4:5
        expect(escena.locator(".resultado-datos")).to_have_text(re.compile(rf"^4:5 · {ancho}×{alto} · .+ · costo 0,05 \$$"))
        pagina.wait_for_function("img => img.complete && img.naturalWidth > 0", arg=escena.locator("img").element_handle())
        archivos_escena.append(archivo)
    _captura(pagina, "4-resultados")

    # La descarga de las escenas: llevan la marca IPTC de imagen hecha con IA y nada del modelo.
    with _descargar(pagina, pagina.get_by_role("link", name="Solo las escenas")) as archivo_zip:
        nombres = sorted(archivo_zip.namelist())
        assert nombres == sorted([f"escenas/{archivo}" for archivo in archivos_escena] + ["resumen.csv"])
        filas = list(csv.DictReader(io.StringIO(archivo_zip.read("resumen.csv").decode("utf-8-sig"))))
        assert len(filas) == 2
        for archivo in archivos_escena:
            datos = archivo_zip.read(f"escenas/{archivo}")
            assert escenas.tiene_marca(datos)
            assert b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia" in datos
            with Image.open(io.BytesIO(datos)) as imagen:
                assert imagen.format == "JPEG" and imagen.mode == "RGB"
                assert archivo.endswith(f"_{imagen.width}x{imagen.height}.jpg")
    with _descargar(pagina, pagina.get_by_role("link", name="Descargar todo (ZIP)")) as archivo_zip:
        assert len(archivo_zip.namelist()) == TOTAL * 4 + 3  # un recorte y tres medidas por foto, 2 escenas y el resumen

    # El gasto de la sesión se ve en Ajustes.
    pagina.click(".zona-boton[data-zona='ajustes']")
    expect(pagina.locator("#gasto-sesion")).to_have_text("Gastado en esta sesión: 0,10 $ de 2,00 $ (quedan 1,90 $).")

    # La siguiente estimación ya usa el costo real medio (0,05 $ por imagen). Con «No, cancelar» no se gasta.
    pagina.click(".zona-boton[data-zona='fotos']")
    pagina.click("#ver-costo")
    expect(pagina.locator("#texto-estimacion")).to_have_text("2 escenas · costo estimado 0,10 $ · ¿Generar?")
    pagina.click("#cancelar-escenas")
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()

    # Si la estimación supera lo que queda del tope de la sesión, no se gasta y la página lo dice.
    pagina.click(".zona-boton[data-zona='ajustes']")
    pagina.fill("#tope-sesion", "0.15")
    pagina.click("#guardar-ajustes")
    expect(pagina.locator("#gasto-sesion")).to_have_text("Gastado en esta sesión: 0,10 $ de 0,15 $ (quedan 0,05 $).")
    pagina.click(".zona-boton[data-zona='fotos']")
    pagina.click("#ver-costo")
    expect(pagina.locator("#error-escenas")).to_have_text(
        "2 escenas · costo estimado 0,10 $. Esto costaría 0,10 $ y en esta sesión te quedan 0,05 $. "
        "Sube el tope en Ajustes o genera menos escenas."
    )
    expect(pagina.locator("#confirmar-escenas")).to_be_hidden()
    _captura(pagina, "4-tope")
    assert len(simulador.peticiones) == antes + 3 and len(gastos.read_text(encoding="utf-8").splitlines()) == 2


def test_5_la_pagina_no_cargo_nada_de_internet_ni_dio_errores(pagina, entorno):
    """En todos los recorridos, cada petición del navegador fue a este computador, y la consola quedó limpia."""
    assert len(entorno.peticiones) > 50
    fuera = [url for url in entorno.peticiones if not url.startswith(entorno.url + "/")]
    assert fuera == [], fuera[:5]
    assert entorno.errores == [], entorno.errores[:5]
    assert entorno.clave not in pagina.content()
    # Y a OpenRouter (simulado) solo se le llamó cuando el usuario lo pidió: probar la clave y generar 2 escenas.
    assert [p["ruta"] for p in entorno.simulador.peticiones] == [
        "/api/v1/key", "/api/v1/key", "/api/v1/images", "/api/v1/images",
    ]
    # La salida del servidor no lleva la clave ni rutas de la carpeta personal.
    salida = entorno.proceso.salida()
    assert "Estudio de fotos abierto en " in salida
    assert entorno.clave not in salida and str(Path.home()) not in salida and "Traceback" not in salida
    assert "#3366cc" not in salida.lower()  # el color del fondo liso tampoco se registra
