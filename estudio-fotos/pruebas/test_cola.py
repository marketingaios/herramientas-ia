"""Paso 6: el estudio y la cola de recorte (con recortadores de mentira, sin modelo y sin internet)."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

import ayudas
from estudio.estudio import ErrorEstudio, Estudio
from estudio.recorte import DescargaFallida, Recortador, RecortadorSimulado


def subir(estudio: Estudio, carpeta: Path, nombre: str, datos: bytes | None = None) -> dict:
    """Hace lo que hace el servidor con una subida: la guarda en un temporal y se la da al estudio."""
    temporal = carpeta / f"subida-{time.monotonic_ns()}"
    temporal.write_bytes(datos if datos is not None else ayudas.foto(1100, 1100))
    return estudio.agregar_foto(temporal, nombre)


class Fabrica:
    """Crea recortadores de mentira y lleva la cuenta de cuántos se crearon y con qué modelo."""

    def __init__(self, clase=RecortadorSimulado):
        self.clase = clase
        self.creados: list[Recortador] = []
        self.modelos: list[str] = []

    def __call__(self, modelo: str) -> Recortador:
        self.modelos.append(modelo)
        recortador = self.clase()
        self.creados.append(recortador)
        return recortador


@pytest.fixture
def fabrica():
    return Fabrica()


@pytest.fixture
def estudio(config, fabrica):
    estudio = Estudio(config, fabrica)
    yield estudio
    estudio.cerrar()


# --- Un lote normal -----------------------------------------------------------------------------------------------


def test_cinco_fotos_se_recortan_en_cola_y_la_barra_llega_a_5_de_5(estudio, tmp_path):
    respuestas = [subir(estudio, tmp_path, f"foto_{n}.jpg") for n in range(1, 6)]
    assert all(r["aceptada"] and r["aviso"] is None for r in respuestas)
    assert estudio.esperar("recorte", 30)

    estado = estudio.publico()
    trabajo = estado["trabajos"]["recorte"]
    assert (trabajo["estado"], trabajo["hechos"], trabajo["total"]) == ("terminado", 5, 5)
    assert re.fullmatch(r"5 de 5 · listo · \d+,\d s en total", trabajo["texto"])
    assert [f["archivo"] for f in estado["fotos"]] == [f"foto_{n}.jpg" for n in range(1, 6)]

    for foto in estado["fotos"]:
        assert foto["estado"] == "lista" and foto["error"] is None and foto["segundos"] is not None
        png = estudio.carpeta_salidas / "recortes" / f"{foto['nombre']}_recorte.png"
        assert foto["recorte"]["archivo"] == png.name
        with Image.open(png) as recorte:  # PNG con transparencia, del tamaño de la foto original
            assert recorte.format == "PNG" and recorte.mode == "RGBA" and recorte.size == (1100, 1100)
            assert recorte.getpixel((5, 5))[3] == 0 and recorte.getpixel((550, 550))[3] == 255
        interna = estudio.foto(foto["id"])
        assert interna.vista.is_file() and interna.vista_recorte.is_file()


def test_el_avance_dice_que_foto_va_y_cuanto_lleva(config, tmp_path):
    class Lento(RecortadorSimulado):
        def mascara(self, imagen):
            time.sleep(0.25)
            return super().mascara(imagen)

    estudio = Estudio(config, Fabrica(Lento))
    try:
        for n in range(1, 4):
            subir(estudio, tmp_path, f"foto_{n}.jpg")
        vistos = set()
        while estudio.publico()["trabajos"]["recorte"]["estado"] == "trabajando":
            vistos.add(estudio.publico()["trabajos"]["recorte"]["texto"])
            time.sleep(0.02)
    finally:
        estudio.cerrar()
    # «3 de 5 · foto_3.jpg · 4,2 s»
    con_foto = [t for t in vistos if re.fullmatch(r"[123] de 3 · foto_[123]\.jpg · \d+,\d s", t)]
    assert {t[0] + t.split(" · ")[1] for t in con_foto} == {"1foto_1.jpg", "2foto_2.jpg", "3foto_3.jpg"}


def test_la_sesion_del_modelo_se_crea_una_sola_vez(estudio, fabrica, tmp_path):
    for n in range(5):
        subir(estudio, tmp_path, f"a{n}.jpg")
    assert estudio.esperar("recorte", 30)
    for n in range(2):  # un segundo lote: se sigue usando la misma sesión
        subir(estudio, tmp_path, f"b{n}.jpg")
    assert estudio.esperar("recorte", 30)

    assert len(fabrica.creados) == 1
    assert (fabrica.creados[0].preparado, fabrica.creados[0].fotos) == (1, 7)
    assert estudio.publico()["trabajos"]["recorte"]["texto"].startswith("2 de 2 · listo")
    assert estudio.publico()["modelo"]["estado"] == "listo"


# --- Lo que puede salir mal -----------------------------------------------------------------------------------------


def test_un_error_en_una_foto_no_rompe_el_lote(config, tmp_path):
    class FallaLaSegunda(RecortadorSimulado):
        def mascara(self, imagen):
            if self.fotos == 1:
                self.fotos += 1
                raise RuntimeError("fallo inventado")
            return super().mascara(imagen)

    estudio = Estudio(config, Fabrica(FallaLaSegunda))
    try:
        for n in range(1, 5):
            subir(estudio, tmp_path, f"foto_{n}.jpg")
        assert estudio.esperar("recorte", 30)
        estado = estudio.publico()
    finally:
        estudio.cerrar()

    assert [f["estado"] for f in estado["fotos"]] == ["lista", "error", "lista", "lista"]
    assert estado["fotos"][1]["error"] == "No se pudo recortar esta foto. Quítala y vuelve a subirla."
    trabajo = estado["trabajos"]["recorte"]
    assert trabajo["texto"].startswith("4 de 4 · 1 con error")
    assert trabajo["errores"] == [{"archivo": "foto_2.jpg", "mensaje": estado["fotos"][1]["error"]}]
    assert "fallo inventado" not in json.dumps(estado)


def test_una_foto_sin_producto_claro_lo_dice(config, tmp_path):
    class SinNada(RecortadorSimulado):
        def mascara(self, imagen):
            return Image.new("L", imagen.size, 0)

    estudio = Estudio(config, Fabrica(SinNada))
    try:
        subir(estudio, tmp_path, "pared.jpg")
        assert estudio.esperar("recorte", 30)
        (foto,) = estudio.publico()["fotos"]
    finally:
        estudio.cerrar()
    assert foto["estado"] == "error" and foto["recorte"] is None
    assert foto["error"] == (
        "No encontramos un producto claro en esta foto. Prueba con el producto más grande y un fondo más simple."
    )


def test_una_foto_que_no_vale_no_entra_en_la_cola(estudio, config, tmp_path):
    respuesta = subir(estudio, tmp_path, "../../notas secretas.jpg", b"esto no es una foto")
    assert respuesta == {"archivo": "notas_secretas.jpg", "aceptada": False, "error": "Este archivo no es una foto JPG, PNG o WEBP."}
    respuesta = subir(estudio, tmp_path, "IMG_0001.HEIC", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 40)
    assert respuesta["aceptada"] is False and respuesta["error"].startswith("Es una foto HEIC (iPhone).")
    respuesta = subir(estudio, tmp_path, "chica.png", ayudas.foto(400, 900, "PNG"))
    assert respuesta["error"] == "La foto mide 400 px de lado corto: se necesitan al menos 500."

    assert estudio.publico()["fotos"] == []
    assert estudio.publico()["trabajos"]["recorte"]["estado"] == "inactivo"
    assert list(config.trabajo.iterdir()) == []  # no queda nada de las rechazadas


def test_una_foto_pequena_se_acepta_con_su_aviso(estudio, tmp_path):
    respuesta = subir(estudio, tmp_path, "mediana.jpg", ayudas.foto(896, 1200))
    assert respuesta["aceptada"] is True
    assert respuesta["aviso"] == "La foto mide 896 px de lado corto: con 1.000 o más se verá mejor."
    assert estudio.esperar("recorte", 30)
    assert estudio.publico()["fotos"][0]["aviso"] == respuesta["aviso"]


def test_dos_fotos_con_el_mismo_nombre_no_se_pisan(estudio, tmp_path):
    primera = subir(estudio, tmp_path, "bolsa.jpg")
    segunda = subir(estudio, tmp_path, "carpeta/bolsa.jpg")
    tercera = subir(estudio, tmp_path, "bolsa.png", ayudas.foto(1100, 1100, "PNG"))
    assert estudio.esperar("recorte", 30)
    assert [r["archivo"] for r in (primera, segunda, tercera)] == ["bolsa.jpg", "bolsa-2.jpg", "bolsa-3.png"]
    recortes = sorted(p.name for p in (estudio.carpeta_salidas / "recortes").iterdir())
    assert recortes == ["bolsa-2_recorte.png", "bolsa-3_recorte.png", "bolsa_recorte.png"]


# --- La descarga del modelo ----------------------------------------------------------------------------------------


class ConDescarga(RecortadorSimulado):
    """Un recortador cuyo modelo «hay que descargar»: la descarga avanza y espera hasta que la prueba la suelta."""

    soltar = threading.Event()
    fallar = False

    def __init__(self):
        super().__init__()
        self.listo = False

    def descargado(self):
        return self.listo

    def descargar(self, avance=None):
        if type(self).fallar:
            raise DescargaFallida()
        avance(312_000_000)
        assert type(self).soltar.wait(20), "la prueba no soltó la descarga"
        self.listo = True


@pytest.fixture
def con_descarga():
    ConDescarga.soltar = threading.Event()
    ConDescarga.fallar = False
    yield ConDescarga
    ConDescarga.soltar.set()


def _esperar_estado(estudio: Estudio, estado: str, segundos: float = 10) -> dict:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        modelo = estudio.publico()["modelo"]
        if modelo["estado"] == estado:
            return modelo
        time.sleep(0.02)
    raise AssertionError(f"el modelo no llegó a «{estado}»: {estudio.publico()['modelo']}")


@pytest.mark.parametrize("calidad, megas", [("maxima", 973), ("rapida", 224)])
def test_mientras_se_descarga_el_modelo_la_pagina_lo_dice_y_todo_lo_demas_sigue(config, tmp_path, con_descarga, calidad, megas):
    estudio = Estudio(config, Fabrica(con_descarga))
    try:
        estudio.cambiar_calidad(calidad)
        subir(estudio, tmp_path, "foto_1.jpg")
        modelo = _esperar_estado(estudio, "descargando")
        assert modelo["mensaje"] == f"Descargando el modelo de recorte ({megas} MB), solo la primera vez"
        assert (modelo["descargado_mb"], modelo["total_mb"]) == (312 if megas > 312 else megas, megas)

        # El resto sigue funcionando: se puede consultar el estado y subir más fotos, que esperan en la cola.
        inicio = time.monotonic()
        assert subir(estudio, tmp_path, "foto_2.jpg")["aceptada"] is True
        estado = estudio.publico()
        assert time.monotonic() - inicio < 2
        assert [f["estado"] for f in estado["fotos"]] == ["en_cola", "en_cola"]
        assert estado["trabajos"]["recorte"]["texto"] == "0 de 2 · Descargando el modelo de recorte, solo la primera vez…"

        con_descarga.soltar.set()
        assert estudio.esperar("recorte", 30)
        assert [f["estado"] for f in estudio.publico()["fotos"]] == ["lista", "lista"]
        assert estudio.publico()["modelo"]["estado"] == "listo"
    finally:
        estudio.cerrar()


def test_si_la_descarga_falla_se_dice_y_se_puede_reintentar(config, tmp_path, con_descarga):
    fabrica = Fabrica(con_descarga)
    estudio = Estudio(config, fabrica)
    try:
        con_descarga.fallar = True
        subir(estudio, tmp_path, "foto_1.jpg")
        modelo = _esperar_estado(estudio, "error")
        assert modelo["mensaje"] == "No se pudo descargar el modelo de recorte. Revisa tu conexión y vuelve a intentarlo."
        estado = estudio.publico()
        assert estado["fotos"][0]["estado"] == "en_cola"  # la foto no se pierde: espera
        assert estado["trabajos"]["recorte"]["mensaje"] == modelo["mensaje"]

        time.sleep(0.3)  # la cola no reintenta por su cuenta
        assert len(fabrica.creados) == 1

        con_descarga.fallar = False
        con_descarga.soltar.set()
        estudio.reintentar_modelo()
        assert estudio.esperar("recorte", 30)
        assert estudio.publico()["fotos"][0]["estado"] == "lista"
        assert estudio.publico()["modelo"]["estado"] == "listo"
    finally:
        estudio.cerrar()


def test_si_el_modelo_no_carga_tambien_se_dice(config, tmp_path):
    class NoCarga(RecortadorSimulado):
        def preparar(self):
            raise MemoryError("sin memoria")

    estudio = Estudio(config, Fabrica(NoCarga))
    try:
        subir(estudio, tmp_path, "foto_1.jpg")
        modelo = _esperar_estado(estudio, "error")
        assert modelo["mensaje"].startswith("No se pudo preparar el modelo de recorte.")
    finally:
        estudio.cerrar()


def test_al_cambiar_la_calidad_se_usa_el_otro_modelo(estudio, fabrica, tmp_path):
    estudio.cambiar_calidad("maxima")
    assert estudio.publico()["modelo"]["etiqueta"] == "Calidad máxima"
    subir(estudio, tmp_path, "a.jpg")
    assert estudio.esperar("recorte", 30)
    estudio.cambiar_calidad("rapida")
    modelo = estudio.publico()["modelo"]
    assert (modelo["nombre"], modelo["etiqueta"], modelo["estado"]) == ("birefnet-general-lite", "Modo rápido", "sin_cargar")
    subir(estudio, tmp_path, "b.jpg")
    assert estudio.esperar("recorte", 30)
    assert fabrica.modelos == ["birefnet-general", "birefnet-general-lite"]
    with pytest.raises(ErrorEstudio):
        estudio.cambiar_calidad("turbo")


def test_en_un_computador_sin_aceleracion_se_avisa_del_modo_rapido(config, monkeypatch):
    from estudio import equipo

    monkeypatch.setattr(equipo, "chip_apple", lambda: False)
    monkeypatch.setattr(equipo, "tarjeta_nvidia", lambda: False)
    estudio = Estudio(config, Fabrica())
    modelo = estudio.publico()["modelo"]
    assert (modelo["nombre"], modelo["etiqueta"]) == ("birefnet-general-lite", "Modo rápido")
    assert modelo["nota"] == (
        "Modo rápido: tu computador no tiene aceleración y usamos un modelo más ligero. Puedes cambiarlo en Ajustes."
    )
    monkeypatch.setattr(equipo, "chip_apple", lambda: True)
    estudio = Estudio(config, Fabrica())
    assert (estudio.publico()["modelo"]["etiqueta"], estudio.publico()["modelo"]["nota"]) == ("Calidad máxima", None)


# --- Quitar fotos y empezar de nuevo --------------------------------------------------------------------------------


def test_quitar_una_foto_no_borra_sus_resultados(estudio, tmp_path):
    foto = subir(estudio, tmp_path, "bolsa.jpg")
    subir(estudio, tmp_path, "taza.jpg")
    assert estudio.esperar("recorte", 30)
    carpeta = estudio.foto(foto["id"]).carpeta

    estudio.quitar_foto(foto["id"])
    assert [f["archivo"] for f in estudio.publico()["fotos"]] == ["taza.jpg"]
    assert not carpeta.exists()  # lo temporal sí se va
    assert (estudio.carpeta_salidas / "recortes" / "bolsa_recorte.png").is_file()  # el resultado se queda
    with pytest.raises(ErrorEstudio) as error:
        estudio.quitar_foto(foto["id"])
    assert error.value.codigo == 404 and str(error.value) == "Esa foto ya no está en la lista."


def test_quitar_una_foto_que_espera_ajusta_el_lote(config, tmp_path, con_descarga):
    estudio = Estudio(config, Fabrica(con_descarga))
    try:
        ids = [subir(estudio, tmp_path, f"foto_{n}.jpg")["id"] for n in range(3)]
        _esperar_estado(estudio, "descargando")
        estudio.quitar_foto(ids[1])
        assert estudio.publico()["trabajos"]["recorte"]["total"] == 2
        con_descarga.soltar.set()
        assert estudio.esperar("recorte", 30)
        assert estudio.publico()["trabajos"]["recorte"]["texto"].startswith("2 de 2 · listo")
    finally:
        estudio.cerrar()


def test_empezar_de_nuevo_vacia_la_lista_pero_no_las_salidas(estudio, config, tmp_path):
    subir(estudio, tmp_path, "bolsa.jpg")
    assert estudio.esperar("recorte", 30)
    sesion = estudio.sesion
    recorte = estudio.carpeta_salidas / "recortes" / "bolsa_recorte.png"

    estudio.empezar_de_nuevo()
    assert estudio.publico()["fotos"] == []
    assert estudio.publico()["trabajos"]["recorte"]["estado"] == "inactivo"
    assert estudio.sesion != sesion  # carpeta nueva: nunca se pisa una sesión anterior
    assert recorte.is_file()
    assert list(config.trabajo.iterdir()) == []

    subir(estudio, tmp_path, "bolsa.jpg")
    assert estudio.esperar("recorte", 30)
    assert (estudio.carpeta_salidas / "recortes" / "bolsa_recorte.png").is_file() and recorte.is_file()


def test_al_arrancar_se_vacia_la_carpeta_de_trabajo(estudio, config):
    (config.trabajo / "resto").mkdir()
    (config.trabajo / "resto" / "vista.jpg").write_bytes(b"x")
    (config.trabajo / "suelto.tmp").write_bytes(b"x")
    estudio.limpiar_trabajo()
    assert list(config.trabajo.iterdir()) == []


def test_el_estado_no_lleva_rutas_del_computador(estudio, tmp_path):
    subir(estudio, tmp_path, "/Users/alguien/Pictures/bolsa.jpg")
    subir(estudio, tmp_path, "rota.jpg", b"\xff\xd8\xff\xe0" + b"basura" * 50)
    assert estudio.esperar("recorte", 30)
    texto = json.dumps(estudio.publico(), ensure_ascii=False)
    assert str(tmp_path) not in texto and str(Path.home()) not in texto and "alguien" not in texto
