"""Paso 5: el recorte, sin el modelo real (recortador simulado) y sin internet."""

from __future__ import annotations

import os
import re

import numpy as np
import pytest
from PIL import Image

import ayudas
from conftest import CARPETA
from estudio import equipo, recorte
from estudio.recorte import (
    MODELOS,
    Recortador,
    RecortadorRembg,
    RecortadorSimulado,
    SinProducto,
    color_del_producto,
    comprobar_modelo,
    crear_sesion,
    limpiar_mascara,
    recortar,
)

CODIGO = sorted((CARPETA / "estudio").glob("*.py"))


# --- Nunca bria-rmbg: el modelo va siempre con su nombre -----------------------------------------------------------


def test_solo_existen_los_dos_modelos_birefnet():
    assert set(MODELOS) == {"birefnet-general", "birefnet-general-lite"}
    assert (MODELOS["birefnet-general"]["mb"], MODELOS["birefnet-general-lite"]["mb"]) == (973, 224)


def test_rembg_conoce_los_dos_modelos_por_ese_nombre():
    """Sin descargar nada: los dos nombres existen tal cual en rembg (uno mal escrito fallaría al primer recorte)."""
    from rembg.sessions import sessions_class

    assert set(MODELOS) <= {clase.name() for clase in sessions_class}


@pytest.mark.parametrize("modelo", [None, "", "bria-rmbg", "u2net", "birefnet-portrait", 3])
def test_cualquier_otro_modelo_se_rechaza_antes_de_tocar_rembg(tmp_path, modelo):
    with pytest.raises(ValueError):
        comprobar_modelo(modelo)
    with pytest.raises(ValueError):
        crear_sesion(modelo, tmp_path)
    with pytest.raises(ValueError):
        RecortadorRembg(modelo, tmp_path)
    assert not list(tmp_path.iterdir())  # ni siquiera se empezó a descargar nada


def test_el_codigo_solo_llama_a_rembg_por_una_puerta_y_con_nombre():
    """Recorre el código: un solo `new_session`, con el nombre del modelo, y nunca `remove()` de rembg."""
    assert CODIGO, "no se encontró el código"
    llamadas = []
    for archivo in CODIGO:
        texto = archivo.read_text(encoding="utf-8")
        sin_comentarios = "\n".join(linea.split("#")[0] for linea in texto.splitlines())
        # (archivo, primer argumento) de cada llamada: el primer argumento tiene que ser el nombre del modelo.
        llamadas += [(archivo.name, m.group(1)) for m in re.finditer(r"new_session\(\s*([^,)\s]*)", sin_comentarios)]
        assert not re.search(r"rembg\.remove|from rembg import .*\bremove\b|rembg\.bg", sin_comentarios), archivo.name
        if archivo.name != "recorte.py":
            assert "bria" not in texto.lower(), f"{archivo.name} nombra el modelo prohibido"
            assert "import rembg" not in texto and "from rembg" not in texto, f"{archivo.name} usa rembg por su cuenta"
    assert llamadas == [("recorte.py", "modelo")], "new_session solo se llama en crear_sesion, con el modelo por nombre"


def test_los_modelos_van_a_la_carpeta_modelos_y_no_a_la_carpeta_personal(tmp_path, monkeypatch):
    monkeypatch.setenv("U2NET_HOME", "/otra/carpeta")  # si el usuario la tuviera definida, ganaría a REMBG_HOME
    monkeypatch.setenv("REMBG_HOME", "/otra/carpeta")
    recorte.preparar_entorno(tmp_path)
    assert os.environ["REMBG_HOME"] == os.environ["U2NET_HOME"] == str(tmp_path.resolve())
    assert recorte.ruta_modelo(tmp_path, "birefnet-general") == tmp_path / "models" / "birefnet-general" / "birefnet-general.onnx"
    recortador = RecortadorRembg("birefnet-general-lite", tmp_path)
    assert not recortador.descargado()
    assert recortador.proveedores == ["CPUExecutionProvider"]


def test_los_mensajes_de_la_descarga_llevan_el_tamano_del_modelo():
    assert recorte.mensaje_descarga("birefnet-general") == "Descargando el modelo de recorte (973 MB), solo la primera vez"
    assert recorte.mensaje_descarga("birefnet-general-lite") == "Descargando el modelo de recorte (224 MB), solo la primera vez"
    assert recorte.MENSAJE_DESCARGANDO == "Descargando el modelo de recorte, solo la primera vez…"
    assert recorte.MENSAJE_DESCARGA_FALLIDA == (
        "No se pudo descargar el modelo de recorte. Revisa tu conexión y vuelve a intentarlo."
    )


# --- El modelo se adapta al computador ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "calidad, apple, nvidia, modelo, etiqueta, con_nota",
    [
        ("automatica", True, False, "birefnet-general", "Calidad máxima", False),
        ("automatica", False, True, "birefnet-general", "Calidad máxima", False),
        ("automatica", False, False, "birefnet-general-lite", "Modo rápido", True),
        ("maxima", False, False, "birefnet-general", "Calidad máxima", False),
        ("rapida", True, True, "birefnet-general-lite", "Modo rápido", False),
    ],
)
def test_el_modelo_segun_el_computador_y_el_ajuste(calidad, apple, nvidia, modelo, etiqueta, con_nota):
    eleccion = equipo.elegir_modelo(calidad, apple=apple, nvidia=nvidia)
    assert (eleccion.modelo, eleccion.etiqueta) == (modelo, etiqueta)
    if con_nota:
        assert eleccion.nota == (
            "Modo rápido: tu computador no tiene aceleración y usamos un modelo más ligero. "
            "Puedes cambiarlo en Ajustes."
        )
    else:
        assert eleccion.nota is None


def test_con_que_se_crea_la_sesion():
    assert equipo.proveedores_para(apple=True, nvidia=False) == ["CPUExecutionProvider"]
    assert equipo.proveedores_para(apple=False, nvidia=True) == ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert equipo.proveedores_para(apple=False, nvidia=False) == ["CPUExecutionProvider"]


# --- La limpieza de la máscara es mínima --------------------------------------------------------------------------


def test_la_limpieza_quita_la_neblina_y_no_muerde_los_bordes():
    todos = np.arange(256, dtype=np.uint8)
    limpio = limpiar_mascara(todos)
    assert (limpio[:13] == 0).all()  # la neblina (menos del 5 %) desaparece
    assert (limpio[243:] == 255).all()  # lo casi opaco queda opaco
    assert (np.diff(limpio.astype(int)) >= 0).all()  # nunca invierte el orden
    assert abs(int(limpio[128]) - 128) <= 1  # la mitad sigue en la mitad: el borde no se mueve
    assert (limpio[128:] >= todos[128:]).all()  # de la mitad para arriba, nunca quita producto
    assert np.abs(limpio.astype(int) - todos.astype(int)).max() <= 13  # y nunca cambia más de un 5 %


def test_el_color_del_borde_no_arrastra_el_fondo_original():
    """Producto rojo sobre fondo verde, con un borde suave: tras la limpieza de color el borde es rojo."""
    color = np.zeros((300, 300, 3), dtype=np.uint8)
    color[...] = (0, 140, 0)
    color[100:200, 100:200] = (200, 30, 30)
    color[100:200, 96:100] = (100, 85, 15)  # el borde de la foto: mitad producto, mitad fondo verde
    alfa = np.zeros((300, 300), dtype=np.uint8)
    alfa[100:200, 100:200] = 255
    alfa[100:200, 96:100] = 128
    limpio = color_del_producto(Image.fromarray(color, "RGB"), alfa)
    borde = limpio[150, 97].astype(int)
    assert borde[0] > 150 and borde[1] < 70, f"el borde sigue manchado de verde: {borde}"
    assert tuple(limpio[150, 150]) == (200, 30, 30)  # el interior no cambia


def test_una_foto_enorme_se_recorta_sin_la_limpieza_de_color(monkeypatch):
    monkeypatch.setattr(recorte, "MEGAPIXELES_LIMPIEZA_COLOR", 0.0001)
    imagen = ayudas.imagen_foto(400, 400)
    alfa = np.full((400, 400), 255, dtype=np.uint8)
    assert (color_del_producto(imagen, alfa) == np.asarray(imagen)).all()


# --- Recortar -----------------------------------------------------------------------------------------------------


class _RecortadorFijo(Recortador):
    """Devuelve una máscara con la parte de producto que se le pida."""

    modelo = "fijo"

    def __init__(self, parte: float, opacidad: int = 255) -> None:
        self.parte, self.opacidad = parte, opacidad

    def mascara(self, imagen):
        datos = np.zeros((imagen.height, imagen.width), dtype=np.uint8)
        datos[: round(imagen.height * self.parte)] = self.opacidad
        return Image.fromarray(datos, "L")


def test_el_recorte_simulado_devuelve_la_foto_con_transparencia():
    imagen = ayudas.imagen_foto(1000, 1200)
    resultado = recortar(imagen, RecortadorSimulado())
    assert resultado.imagen.mode == "RGBA" and resultado.imagen.size == (1000, 1200)
    assert 0.25 < resultado.cobertura < 0.40
    alfa = np.asarray(resultado.imagen.getchannel("A"))
    assert alfa[600, 500] == 255 and alfa[5, 5] == 0
    izquierda, arriba, derecha, abajo = resultado.caja
    assert abs(izquierda - 220) <= 4 and abs(derecha - 780) <= 4 and abs(arriba - 168) <= 4 and abs(abajo - 1032) <= 4
    assert resultado.segundos_modelo >= 0


@pytest.mark.parametrize("parte, hay_producto", [(0.0, False), (0.03, False), (0.06, True), (0.5, True), (0.94, True), (0.97, False), (1.0, False)])
def test_sin_un_producto_claro_se_dice(parte, hay_producto):
    imagen = ayudas.imagen_foto(800, 800)
    if hay_producto:
        assert abs(recortar(imagen, _RecortadorFijo(parte)).cobertura - parte) < 0.01
    else:
        with pytest.raises(SinProducto) as error:
            recortar(imagen, _RecortadorFijo(parte))
        assert str(error.value) == (
            "No encontramos un producto claro en esta foto. Prueba con el producto más grande y un fondo más simple."
        )


def test_una_mascara_que_es_solo_neblina_no_es_un_producto():
    with pytest.raises(SinProducto):
        recortar(ayudas.imagen_foto(800, 800), _RecortadorFijo(0.5, opacidad=10))


def test_una_mascara_de_otra_medida_se_ajusta_a_la_foto():
    class Pequeno(Recortador):
        def mascara(self, imagen):
            return RecortadorSimulado().mascara(Image.new("RGB", (256, 256)))

    assert recortar(ayudas.imagen_foto(900, 700), Pequeno()).imagen.size == (900, 700)
