"""Paso 4: fondo blanco puro, encuadre, medida, formato y peso de cada plataforma."""

from __future__ import annotations

import io
import re

import numpy as np
import pytest
from PIL import Image, ImageCms

import ayudas
from conftest import CARPETA
from estudio.encuadre import (
    MARGEN_JPEG,
    SinProducto,
    caja_producto,
    calcular_encuadre,
    componer,
    exportar,
)
from estudio.plataformas import Plataforma, cargar

PLATAFORMAS = cargar(CARPETA / "plataformas.json")
POR_ID = {p.id: p for p in PLATAFORMAS}

# Recortes inventados: (ancho, alto, caja del producto, forma). Altos, anchos, pequeños y descentrados.
RECORTES = {
    "alto": (1600, 2000, (500, 200, 1100, 1900), "rectangulo"),
    "ancho": (2400, 1600, (300, 500, 2200, 1200), "elipse"),
    "descentrado": (3000, 3000, (100, 150, 1900, 1700), "elipse"),
    "pequeno": (1024, 1024, (380, 300, 700, 760), "rectangulo"),
}


def _recorte(nombre: str) -> Image.Image:
    ancho, alto, caja, forma = RECORTES[nombre]
    return ayudas.recorte(ancho, alto, caja, forma)


@pytest.fixture(scope="module")
def exportadas(tmp_path_factory):
    """Todas las combinaciones de recorte y plataforma, exportadas una sola vez."""
    carpeta = tmp_path_factory.mktemp("medidas")
    resultado = {}
    for nombre in RECORTES:
        recorte = _recorte(nombre)
        for plataforma in PLATAFORMAS:
            resultado[nombre, plataforma.id] = exportar(recorte, nombre, plataforma, carpeta / plataforma.id)
    return resultado


CASOS = [(nombre, plataforma.id) for nombre in RECORTES for plataforma in PLATAFORMAS]


@pytest.mark.parametrize("nombre, plataforma", CASOS)
def test_todo_el_fondo_es_blanco_puro(exportadas, nombre, plataforma):
    salida = exportadas[nombre, plataforma]
    imagen = Image.open(salida.ruta).convert("RGB")
    datos = np.array(imagen)
    izquierda, arriba, derecha, abajo = ayudas.caja_no_blanca(imagen)
    assert MARGEN_JPEG <= 8
    # Las cuatro esquinas y los cuatro bordes del archivo.
    for esquina in (datos[0, 0], datos[0, -1], datos[-1, 0], datos[-1, -1]):
        assert tuple(esquina) == (255, 255, 255)
    assert datos[0].min() == 255 and datos[-1].min() == 255 and datos[:, 0].min() == 255 and datos[:, -1].min() == 255
    # Todo lo que queda fuera del producto: 255, 255, 255, sin grises.
    datos[max(0, arriba - MARGEN_JPEG) : abajo + MARGEN_JPEG, max(0, izquierda - MARGEN_JPEG) : derecha + MARGEN_JPEG] = 255
    assert datos.min() == 255
    assert not salida.avisos or all("blanco" not in aviso for aviso in salida.avisos)


@pytest.mark.parametrize("nombre, plataforma", CASOS)
def test_el_producto_esta_centrado_y_ocupa_lo_que_pide_la_plataforma(exportadas, nombre, plataforma):
    salida = exportadas[nombre, plataforma]
    pedido = POR_ID[plataforma].porcentaje
    imagen = Image.open(salida.ruta)
    ancho, alto = imagen.size
    izquierda, arriba, derecha, abajo = ayudas.caja_no_blanca(imagen)

    ocupado = max((derecha - izquierda) / ancho, (abajo - arriba) / alto) * 100
    assert abs(ocupado - pedido) <= 1, f"ocupa el {ocupado:.1f} % y la plataforma pide el {pedido} %"
    assert abs(salida.porcentaje - pedido) <= 1  # lo que irá a resumen.csv

    centro_x = (izquierda + derecha) / 2 / ancho * 100
    centro_y = (arriba + abajo) / 2 / alto * 100
    assert abs(centro_x - 50) <= 1 and abs(centro_y - 50) <= 1, f"centro en {centro_x:.1f} %, {centro_y:.1f} %"

    # El producto entero: no toca ningún borde.
    assert izquierda > 0 and arriba > 0 and derecha < ancho and abajo < alto


@pytest.mark.parametrize("nombre, plataforma", CASOS)
def test_medida_formato_color_y_peso(exportadas, nombre, plataforma):
    salida = exportadas[nombre, plataforma]
    definicion = POR_ID[plataforma]
    imagen = Image.open(salida.ruta)

    assert imagen.format == "JPEG" and imagen.mode == "RGB"
    if definicion.sin_ampliar:
        assert definicion.ancho_minimo <= imagen.width <= definicion.ancho
        assert definicion.alto_minimo <= imagen.height <= definicion.alto
    else:
        assert imagen.size == (definicion.ancho, definicion.alto)
    assert (salida.ancho, salida.alto) == imagen.size

    perfil = ImageCms.ImageCmsProfile(io.BytesIO(imagen.info["icc_profile"]))
    assert "sRGB" in ImageCms.getProfileDescription(perfil)
    assert not imagen.getexif()  # ningún metadato de la foto original

    peso = salida.ruta.stat().st_size
    assert peso == salida.peso
    if definicion.peso_maximo_bytes is not None:
        assert peso <= definicion.peso_maximo_bytes
    assert salida.calidad <= 90


@pytest.mark.parametrize("nombre, plataforma", CASOS)
def test_el_nombre_del_archivo(exportadas, nombre, plataforma):
    salida = exportadas[nombre, plataforma]
    assert salida.archivo == f"{nombre}_{plataforma}_{salida.ancho}x{salida.alto}.jpg"
    assert salida.ruta.name == salida.archivo
    assert re.fullmatch(r"[A-Za-z0-9_-]+_[a-z0-9-]+_\d+x\d+\.jpg", salida.archivo)


def test_no_se_anade_nada_a_la_foto(exportadas):
    """Sin texto, logo, borde, sombra ni marca de agua: fuera del producto solo hay blanco (comprobado arriba),
    y dentro, los colores del producto."""
    salida = exportadas["pequeno", "mercadolibre"]
    imagen = Image.open(salida.ruta).convert("RGB")
    izquierda, arriba, derecha, abajo = ayudas.caja_no_blanca(imagen)
    centro = np.asarray(imagen)[arriba + 30 : abajo - 30, izquierda + 30 : derecha - 30].reshape(-1, 3).mean(axis=0)
    assert np.abs(centro - np.array([150, 70, 40])).max() < 6


# --- La regla de Amazon: no agrandar las fotos pequeñas -----------------------------------------------------------


@pytest.mark.parametrize(
    "lado_producto, lienzo, ampliada",
    [
        (2400, 2000, False),  # producto grande: 2000×2000, reducido
        (1700, 2000, False),  # justo el 85 % de 2000
        (1500, 1764, False),  # la medida baja a 1500 ÷ 0,85, sin ampliar
        (1000, 1176, False),
        (850, 1000, False),  # justo el 85 % de 1000
        (600, 1000, True),  # ni con el mínimo: hay que ampliar, y se avisa
    ],
)
def test_amazon_baja_la_medida_para_no_ampliar(tmp_path, lado_producto, lienzo, ampliada):
    recorte = ayudas.recorte(lado_producto + 200, lado_producto + 200, (100, 100, 100 + lado_producto, 100 + lado_producto - 80))
    salida = exportar(recorte, "foto", POR_ID["amazon"], tmp_path)
    assert (salida.ancho, salida.alto) == (lienzo, lienzo)
    if ampliada:
        assert salida.escala > 1
        assert salida.avisos == [f"ampliada ×{str(round(850 / lado_producto, 1)).replace('.', ',')}: Amazon pide no agrandar las fotos pequeñas"]
    else:
        assert salida.escala <= 1.0
        assert salida.avisos == []
    assert abs(salida.porcentaje - 85) <= 1


def test_en_las_demas_se_avisa_si_se_amplia_mas_del_doble(tmp_path):
    chico = ayudas.recorte(700, 700, (100, 100, 525, 400))  # 425 px de lado largo → ×2,4 en Mercado Libre? no: 1140/425
    salida = exportar(chico, "chica", POR_ID["catalogo-meta"], tmp_path)  # 1024 × 0,85 = 870 → ×2,05
    assert salida.avisos == ["ampliada ×2,0, puede verse borrosa"]
    salida = exportar(chico, "chica", POR_ID["shopify"], tmp_path)  # 2048 × 0,85 = 1741 → ×4,1
    assert salida.avisos == ["ampliada ×4,1, puede verse borrosa"]

    normal = ayudas.recorte(1200, 1200, (100, 100, 1000, 900))  # ×1,9 en Shopify: sin aviso
    assert exportar(normal, "normal", POR_ID["shopify"], tmp_path).avisos == []


def test_el_aviso_de_la_ficha():
    plataforma = Plataforma(id="tienda", nombre="Tienda", ancho=1200, alto=1200, porcentaje=100)
    encuadre = calcular_encuadre(500, 300, plataforma)
    assert round(encuadre.escala, 1) == 2.4


# --- El peso baja la calidad --------------------------------------------------------------------------------------


def _con_ruido(lado: int) -> Image.Image:
    """Un recorte muy difícil de comprimir (ruido puro), para forzar el límite de peso."""
    datos = np.random.default_rng(3).integers(0, 255, size=(lado, lado, 4), dtype=np.uint8)
    datos[..., 3] = 255
    return Image.fromarray(datos, "RGBA")


def test_la_calidad_baja_si_el_archivo_supera_el_peso(tmp_path):
    salida = exportar(_con_ruido(1400), "ruido", POR_ID["tiendanube"], tmp_path)
    assert salida.peso <= 500_000
    assert salida.calidad < 90
    assert salida.avisos == []
    # La misma foto, sin límite de peso, se queda en calidad 90.
    assert exportar(_con_ruido(1400), "ruido", POR_ID["instagram"], tmp_path).calidad == 90


def test_si_ni_con_la_calidad_minima_cabe_se_avisa(tmp_path):
    estricta = Plataforma(id="estricta", nombre="Estricta", ancho=1280, alto=1280, porcentaje=85, peso_maximo_kb=40)
    salida = exportar(_con_ruido(1400), "ruido", estricta, tmp_path)
    assert salida.peso > 40_000
    assert len(salida.avisos) == 1 and "no se pudo bajar al máximo de Estricta (40 KB)" in salida.avisos[0]


# --- Casos límite -------------------------------------------------------------------------------------------------


def test_un_recorte_vacio_no_tiene_producto(tmp_path):
    vacio = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    assert caja_producto(np.asarray(vacio.getchannel("A"))) is None
    with pytest.raises(SinProducto):
        exportar(vacio, "vacio", POR_ID["shopify"], tmp_path)


def test_la_neblina_de_la_mascara_no_mancha_el_blanco():
    """Un alfa muy bajo repartido por la foto (por debajo del 5 %) no cuenta como producto ni deja grises."""
    recorte = ayudas.recorte(1500, 1500, (400, 400, 1100, 1100))
    datos = np.array(recorte)
    datos[..., 3] = np.maximum(datos[..., 3], 9)  # neblina en toda la foto
    datos[..., :3] = np.where(datos[..., 3:4] == 9, 20, datos[..., :3])
    imagen, encuadre = componer(Image.fromarray(datos, "RGBA"), POR_ID["mercadolibre"])
    assert abs(encuadre.porcentaje - 95) <= 0.5
    pixeles = np.array(imagen)
    x, y = encuadre.posicion
    pixeles[y : y + encuadre.producto[1], x : x + encuadre.producto[0]] = 255
    assert pixeles.min() == 255


def test_un_borde_suave_se_mezcla_con_blanco_y_no_con_el_fondo_original():
    """Los píxeles medio transparentes del borde quedan entre el color del producto y el blanco."""
    datos = np.zeros((600, 600, 4), dtype=np.uint8)
    datos[..., :3] = (0, 120, 0)  # el «fondo original» verde sigue en los píxeles transparentes
    datos[150:450, 150:450] = (200, 40, 40, 255)
    datos[150:450, 140:150] = (200, 40, 40, 128)  # borde suave
    imagen, encuadre = componer(Image.fromarray(datos, "RGBA"), Plataforma("t", "T", 620, 620, 50))
    fila = np.asarray(imagen)[310]
    borde = fila[encuadre.posicion[0] + 3]
    assert borde[0] > 215 and 130 < borde[1] < 170 and 130 < borde[2] < 170  # rojo mezclado con blanco
    assert not (fila[:, 1].astype(int) > fila[:, 0].astype(int) + 10).any()  # ni rastro del verde
