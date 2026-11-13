"""Paso 7: fondo blanco y medidas en lote, y la descarga en ZIP con resumen.csv."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from PIL import Image

import ayudas
from estudio.estudio import ErrorEstudio, Estudio
from test_cola import subir

TRES = ["mercadolibre", "amazon", "instagram"]


@pytest.fixture
def estudio(config, tmp_path):
    """Un estudio con dos fotos ya recortadas (recorte simulado)."""
    estudio = Estudio(config)
    subir(estudio, tmp_path, "bolsa_mesa.jpg", ayudas.foto(1024, 1024))
    subir(estudio, tmp_path, "taza_logo.jpg", ayudas.foto(896, 1200))
    assert estudio.esperar("recorte", 30)
    yield estudio
    estudio.cerrar()


def _ids(estudio: Estudio) -> list[str]:
    return [foto["id"] for foto in estudio.publico()["fotos"]]


def _leer_zip(ruta: Path) -> tuple[list[str], list[dict], bytes]:
    with zipfile.ZipFile(ruta) as archivo:
        assert archivo.testzip() is None
        nombres = sorted(archivo.namelist())
        crudo = archivo.read("resumen.csv")
    filas = list(csv.DictReader(io.StringIO(crudo.decode("utf-8-sig"))))
    return nombres, filas, crudo


# --- El lote de medidas ---------------------------------------------------------------------------------------------


def test_cada_foto_sale_en_cada_plataforma_elegida(estudio):
    assert estudio.generar_medidas(_ids(estudio), TRES) == 6
    assert estudio.esperar("medidas", 30)

    estado = estudio.publico()
    trabajo = estado["trabajos"]["medidas"]
    assert re.fullmatch(r"6 de 6 · listo · \d+,\d s en total", trabajo["texto"]) and trabajo["errores"] == []

    bolsa, taza = estado["fotos"]
    assert [s["plataforma"] for s in bolsa["salidas"]] == TRES  # en el orden de plataformas.json
    assert [s["archivo"] for s in bolsa["salidas"]] == [
        "bolsa_mesa_mercadolibre_1200x1200.jpg",
        "bolsa_mesa_amazon_1000x1000.jpg",  # foto de 1024 px: Amazon baja al mínimo
        "bolsa_mesa_instagram_1080x1350.jpg",
    ]
    assert [s["medida"] for s in taza["salidas"]] == ["1200×1200", "1022×1022", "1080×1350"]
    assert [s["porcentaje"] for s in bolsa["salidas"]] == ["95", "85", "80"]
    assert bolsa["salidas"][1]["avisos"] == ["ampliada ×1,1: Amazon pide no agrandar las fotos pequeñas"]
    assert taza["salidas"][1]["avisos"] == []  # el producto de la taza ya mide lo justo: sin ampliar

    for foto in (bolsa, taza):
        for salida in foto["salidas"]:
            ruta = estudio.carpeta_salidas / salida["plataforma"] / salida["archivo"]
            assert ruta.is_file() and ruta.stat().st_size == salida["peso"]
            assert estudio.archivo(foto["id"], salida["archivo"]) == ruta
            assert salida["url"] == f"/api/archivos/{foto['id']}/{salida['archivo']}"
            with Image.open(ruta) as imagen:
                assert imagen.format == "JPEG" and imagen.getpixel((0, 0)) == (255, 255, 255)


def test_se_pueden_anadir_plataformas_despues_y_volver_a_generar(estudio):
    estudio.generar_medidas(_ids(estudio)[:1], ["shopify"])
    assert estudio.esperar("medidas", 30)
    estudio.generar_medidas(_ids(estudio), ["shopify", "tiendanube"])
    assert estudio.esperar("medidas", 30)
    bolsa, taza = estudio.publico()["fotos"]
    assert [s["plataforma"] for s in bolsa["salidas"]] == ["shopify", "tiendanube"]
    assert [s["plataforma"] for s in taza["salidas"]] == ["shopify", "tiendanube"]
    assert len(list((estudio.carpeta_salidas / "shopify").iterdir())) == 2  # regenerar no duplica archivos


def test_hay_que_elegir_fotos_recortadas_y_plataformas(estudio):
    with pytest.raises(ErrorEstudio) as error:
        estudio.generar_medidas(_ids(estudio), [])
    assert str(error.value) == "Elige al menos una plataforma."
    with pytest.raises(ErrorEstudio):
        estudio.generar_medidas(_ids(estudio), ["no-existe"])
    with pytest.raises(ErrorEstudio) as error:
        estudio.generar_medidas(["no-existe"], TRES)
    assert str(error.value) == "Elige al menos una foto ya recortada."
    assert estudio.publico()["trabajos"]["medidas"]["estado"] == "inactivo"


def test_si_plataformas_json_tiene_un_error_se_dice_y_no_se_genera(config, tmp_path):
    rota = tmp_path / "herramienta"
    rota.mkdir()
    (rota / "plataformas.json").write_text("{ esto no es json", encoding="utf-8")
    estudio = Estudio(dataclasses.replace(config, carpeta=rota))
    try:
        foto = subir(estudio, tmp_path, "bolsa.jpg")
        assert estudio.esperar("recorte", 30)
        with pytest.raises(ErrorEstudio) as error:
            estudio.generar_medidas([foto["id"]], TRES)
        assert str(error.value).startswith("plataformas.json tiene un error: no es un JSON válido")
        assert str(tmp_path) not in str(error.value)
        assert estudio.publico()["fotos"][0]["salidas"] == []
    finally:
        estudio.cerrar()


def test_solo_se_sirven_los_archivos_que_el_estudio_creo(estudio, config):
    estudio.generar_medidas(_ids(estudio), ["shopify"])
    assert estudio.esperar("medidas", 30)
    foto_id = _ids(estudio)[0]
    assert estudio.archivo(foto_id, "bolsa_mesa_recorte.png").is_file()
    assert estudio.archivo(foto_id, "bolsa_mesa_shopify_2048x2048.jpg").is_file()
    (config.datos_raiz / ".env").write_text("SECRETO=1\n", encoding="utf-8")  # un .env de mentira en la carpeta temporal
    for nombre in ("../../../.env", "..%2F.env", ".env", "original", "taza_logo_recorte.png", "/etc/passwd", ""):
        with pytest.raises(ErrorEstudio) as error:
            estudio.archivo(foto_id, nombre)
        assert error.value.codigo == 404
    with pytest.raises(ErrorEstudio):
        estudio.archivo("no-existe", "bolsa_mesa_recorte.png")


# --- La descarga ------------------------------------------------------------------------------------------------------


def test_el_zip_de_todo_lleva_recortes_plataformas_y_resumen(estudio):
    estudio.generar_medidas(_ids(estudio), TRES)
    assert estudio.esperar("medidas", 30)
    ruta = estudio.descargar()
    assert ruta.name == f"estudio-fotos_{estudio.sesion}.zip"
    nombres, filas, crudo = _leer_zip(ruta)

    assert nombres == sorted([
        "recortes/bolsa_mesa_recorte.png", "recortes/taza_logo_recorte.png",
        "mercadolibre/bolsa_mesa_mercadolibre_1200x1200.jpg", "mercadolibre/taza_logo_mercadolibre_1200x1200.jpg",
        "amazon/bolsa_mesa_amazon_1000x1000.jpg", "amazon/taza_logo_amazon_1022x1022.jpg",
        "instagram/bolsa_mesa_instagram_1080x1350.jpg", "instagram/taza_logo_instagram_1080x1350.jpg",
        "resumen.csv",
    ])

    assert crudo.startswith(b"\xef\xbb\xbf")  # BOM: Excel lee bien los acentos
    assert list(filas[0]) == ["archivo", "plataforma", "medida", "peso_kb", "porcentaje_producto", "avisos"]
    assert len(filas) == 8
    por_archivo = {fila["archivo"]: fila for fila in filas}
    assert set(por_archivo) == {Path(nombre).name for nombre in nombres if nombre != "resumen.csv"}

    fila = por_archivo["bolsa_mesa_mercadolibre_1200x1200.jpg"]
    assert (fila["plataforma"], fila["medida"], fila["porcentaje_producto"], fila["avisos"]) == ("Mercado Libre", "1200x1200", "95,0", "")
    fila = por_archivo["bolsa_mesa_amazon_1000x1000.jpg"]
    assert fila["avisos"] == "ampliada ×1,1: Amazon pide no agrandar las fotos pequeñas"
    fila = por_archivo["taza_logo_recorte.png"]
    assert (fila["plataforma"], fila["medida"]) == ("Recorte (PNG con transparencia)", "896x1200")
    assert fila["avisos"] == "La foto mide 896 px de lado corto: con 1.000 o más se verá mejor."
    assert 60 < float(fila["porcentaje_producto"].replace(",", ".")) < 80

    with zipfile.ZipFile(ruta) as archivo:
        for nombre in nombres:
            if nombre != "resumen.csv":
                en_disco = (estudio.carpeta_salidas / nombre).stat().st_size
                assert archivo.getinfo(nombre).file_size == en_disco
                assert int(por_archivo[Path(nombre).name]["peso_kb"]) == -(-en_disco // 1000)


def test_se_puede_descargar_una_plataforma_a_la_vez(estudio):
    estudio.generar_medidas(_ids(estudio), TRES)
    assert estudio.esperar("medidas", 30)

    ruta = estudio.descargar("amazon")
    assert ruta.name == f"estudio-fotos_{estudio.sesion}_amazon.zip"
    nombres, filas, _ = _leer_zip(ruta)
    assert nombres == ["amazon/bolsa_mesa_amazon_1000x1000.jpg", "amazon/taza_logo_amazon_1022x1022.jpg", "resumen.csv"]
    assert [fila["plataforma"] for fila in filas] == ["Amazon", "Amazon"]

    nombres, filas, _ = _leer_zip(estudio.descargar("recortes"))
    assert nombres == ["recortes/bolsa_mesa_recorte.png", "recortes/taza_logo_recorte.png", "resumen.csv"]


def test_descargas_que_no_se_pueden_hacer(estudio, config, tmp_path):
    with pytest.raises(ErrorEstudio) as error:
        estudio.descargar("../../etc")
    assert error.value.codigo == 404 and str(error.value) == "Esa plataforma no existe."
    with pytest.raises(ErrorEstudio) as error:
        estudio.descargar("shopify")  # existe, pero aún no se generó nada para ella
    assert str(error.value) == "Todavía no hay archivos para descargar."

    vacio = Estudio(config)
    with pytest.raises(ErrorEstudio):
        vacio.descargar()


def test_ni_el_zip_ni_el_resumen_llevan_rutas_del_computador(estudio, tmp_path):
    estudio.generar_medidas(_ids(estudio), TRES)
    assert estudio.esperar("medidas", 30)
    ruta = estudio.descargar()
    nombres, filas, crudo = _leer_zip(ruta)
    todo = json.dumps(filas, ensure_ascii=False) + " ".join(nombres) + json.dumps(estudio.publico(), ensure_ascii=False)
    assert str(tmp_path) not in todo and str(Path.home()) not in todo
    assert all(not nombre.startswith("/") and ".." not in nombre for nombre in nombres)
    assert ruta.parent == estudio.config.trabajo / "descargas"  # el ZIP es temporal: se hace en trabajo/


def test_el_peso_se_escribe_como_se_lee():
    from estudio.descargas import texto_bytes

    assert texto_bytes(183_400) == "184 KB"
    assert texto_bytes(999_001) == "1000 KB"
    assert texto_bytes(1_240_000) == "1,2 MB"
