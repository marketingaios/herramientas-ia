"""De punta a punta: la página en un navegador de verdad (Playwright con Chromium sin ventana).

El servidor se arranca como lo arranca el usuario (`python -m estudio`), en otro puerto, con `NO_ABRIR_NAVEGADOR=1`,
los datos en una carpeta temporal, el modelo real de recorte y OpenRouter simulado. Se pasan con:

    uv run --group pruebas pytest -m e2e

Los recorridos van en orden y comparten la misma página, como una sesión de uso.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import MUESTRAS

pytestmark = pytest.mark.e2e

ENLACE_FIRMA = "https://marketingaios.com/?origen=herramienta-estudio-fotos"
CAPTURAS = os.environ.get("E2E_CAPTURAS", "")  # una carpeta donde dejar capturas de pantalla (opcional)


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


def test_1_subir_las_cinco_muestras_y_ver_los_cinco_recortes(pagina, entorno):
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

    # Sube las 5 fotos de muestras/ y espera la barra hasta «5 de 5».
    muestras = sorted(MUESTRAS.glob("*.jpg"))
    assert len(muestras) == 5
    pagina.set_input_files("#elegir-fotos", [str(ruta) for ruta in muestras])
    expect(pagina.locator("#lista-fotos .foto")).to_have_count(5)
    expect(pagina.locator("#avance-recorte")).to_be_visible()
    expect(pagina.locator("#texto-recorte")).to_contain_text(" de 5")  # la barra, mientras trabaja
    _captura(pagina, "1-recortando")
    expect(pagina.locator("#texto-recorte")).to_contain_text("5 de 5 · listo", timeout=600_000)
    assert pagina.locator("#barra-recorte").evaluate("barra => barra.style.width") == "100%"
    pagina.wait_for_function(  # la barra llega hasta el final
        "() => { const b = document.querySelector('#barra-recorte'); return b.getBoundingClientRect().width >= b.parentElement.getBoundingClientRect().width - 1; }"
    )

    # Las dos fotos de menos de 1.000 px de lado corto se aceptan con su aviso.
    expect(pagina.locator("#avisos-subida li")).to_have_count(2)
    expect(pagina.locator("#avisos-subida li").first).to_contain_text("mide 896 px de lado corto: con 1.000 o más se verá mejor")

    # Se ven los 5 recortes: antes y después, con el deslizador, sobre el fondo de cuadros.
    tarjetas = pagina.locator("#lista-fotos .foto")
    pagina.wait_for_function(
        "() => [...document.querySelectorAll('#lista-fotos img')].every(img => img.hidden || (img.complete && img.naturalWidth > 0))"
    )
    nombres = []
    for indice in range(5):
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
    assert nombres == [ruta.name for ruta in muestras]

    # El deslizador mueve la línea entre el antes y el después.
    primera = tarjetas.first
    assert primera.locator(".comparador").evaluate("caja => getComputedStyle(caja).getPropertyValue('--corte').trim()") == "50%"
    primera.locator(".deslizador").evaluate("d => { d.value = '80'; d.dispatchEvent(new Event('input', {bubbles: true})); }")
    assert primera.locator(".comparador").evaluate("caja => getComputedStyle(caja).getPropertyValue('--corte').trim()") == "80%"
    _captura(pagina, "1-recortes")
