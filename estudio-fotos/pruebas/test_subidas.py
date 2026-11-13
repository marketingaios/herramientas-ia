"""Paso 3: las subidas. Tipo por contenido, HEIC, peso, lado corto, megapíxeles, foto dañada y nombre limpio."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

import ayudas
from estudio import subidas
from estudio.subidas import ErrorFoto, abrir_normalizada, detectar_tipo, limpiar_nombre, validar


def _guardar(tmp_path: Path, nombre: str, datos: bytes) -> Path:
    ruta = tmp_path / nombre
    ruta.write_bytes(datos)
    return ruta


def _mensaje(ruta: Path, **opciones) -> str:
    with pytest.raises(ErrorFoto) as error:
        validar(ruta, **opciones)
    return str(error.value)


# --- El tipo se comprueba por el contenido, no por el nombre -----------------------------------------------------


@pytest.mark.parametrize("formato, tipo", [("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp")])
def test_acepta_jpg_png_y_webp(tmp_path, formato, tipo):
    ruta = _guardar(tmp_path, "foto.bin", ayudas.foto(1200, 1000, formato))
    valida = validar(ruta)
    assert (valida.tipo, valida.ancho, valida.alto, valida.aviso) == (tipo, 1200, 1000, None)


def test_un_png_con_nombre_de_jpg_se_reconoce_por_su_contenido(tmp_path):
    ruta = _guardar(tmp_path, "en_realidad_es_png.jpg", ayudas.foto(1100, 1100, "PNG"))
    assert validar(ruta).tipo == "png"


@pytest.mark.parametrize(
    "datos",
    [b"hola, soy un texto", b"GIF89a" + b"\x00" * 64, b"%PDF-1.7\n" + b"\x00" * 64, b"", b"<svg xmlns='http://www.w3.org/2000/svg'/>"],
)
def test_lo_que_no_es_una_foto_no_se_acepta_aunque_se_llame_jpg(tmp_path, datos):
    assert _mensaje(_guardar(tmp_path, "foto.jpg", datos)) == "Este archivo no es una foto JPG, PNG o WEBP."


@pytest.mark.parametrize("marca", [b"heic", b"heix", b"mif1", b"hevc"])
def test_una_foto_heic_tiene_su_mensaje_con_la_solucion(tmp_path, marca):
    datos = b"\x00\x00\x00\x18ftyp" + marca + b"\x00" * 64
    assert detectar_tipo(datos) == "heic"
    assert _mensaje(_guardar(tmp_path, "IMG_0042.HEIC", datos)) == (
        "Es una foto HEIC (iPhone). Expórtala como JPG, o en el iPhone ve a Ajustes › Cámara › Formatos "
        "y elige «Más compatible»."
    )


# --- Tamaño -------------------------------------------------------------------------------------------------------


def test_menos_de_500_px_de_lado_corto_no_se_acepta(tmp_path):
    ruta = _guardar(tmp_path, "chica.jpg", ayudas.foto(1400, 499))
    assert _mensaje(ruta) == "La foto mide 499 px de lado corto: se necesitan al menos 500."


@pytest.mark.parametrize("lado, con_aviso", [(500, True), (999, True), (1000, False), (1600, False)])
def test_menos_de_1000_px_se_acepta_con_aviso(tmp_path, lado, con_aviso):
    valida = validar(_guardar(tmp_path, "foto.jpg", ayudas.foto(lado, 1800)))
    if con_aviso:
        assert valida.aviso == f"La foto mide {lado} px de lado corto: con 1.000 o más se verá mejor."
    else:
        assert valida.aviso is None


def test_mas_de_25_mb_no_se_acepta(tmp_path):
    ruta = _guardar(tmp_path, "foto.jpg", ayudas.foto(1200, 1200))
    assert _mensaje(ruta, peso=31 * 1024 * 1024 + 400_000) == "La foto pesa 31,4 MB: el máximo es 25."
    assert _mensaje(ruta, peso=25 * 1024 * 1024 + 1) == "La foto pesa 25,1 MB: el máximo es 25."
    assert validar(ruta, peso=25 * 1024 * 1024).tipo == "jpeg"  # justo 25 MB sí


def test_una_foto_de_mas_de_25_mb_de_verdad(tmp_path):
    ruta = _guardar(tmp_path, "enorme.jpg", ayudas.foto(600, 600) + b"\x00" * (26 * 1024 * 1024))
    assert _mensaje(ruta).startswith("La foto pesa 26,")


def test_demasiados_megapixeles_se_rechaza_antes_de_decodificar(tmp_path):
    memoria = io.BytesIO()
    Image.new("L", (8000, 7000), 200).save(memoria, "PNG")  # 56 megapíxeles en un archivo diminuto
    mensaje = _mensaje(_guardar(tmp_path, "gigante.png", memoria.getvalue()))
    assert mensaje == "La foto mide 56 megapíxeles: el máximo es 50. Redúcela y vuelve a subirla."


def test_una_bomba_de_descompresion_no_se_abre(tmp_path):
    memoria = io.BytesIO()
    Image.new("1", (11000, 10000)).save(memoria, "PNG")  # 110 megapíxeles en unos pocos KB
    assert len(memoria.getvalue()) < 100_000
    mensaje = _mensaje(_guardar(tmp_path, "bomba.png", memoria.getvalue()))
    assert "megapíxeles: el máximo es 50" in mensaje


# --- Fotos dañadas ------------------------------------------------------------------------------------------------


def test_una_foto_cortada_a_la_mitad_esta_danada(tmp_path):
    datos = ayudas.foto(1200, 1200)
    ruta = _guardar(tmp_path, "cortada.jpg", datos[: len(datos) // 2])
    assert _mensaje(ruta) == "No se puede abrir esta foto: puede estar dañada."


@pytest.mark.parametrize("cabecera", [b"\xff\xd8\xff\xe0", b"\x89PNG\r\n\x1a\n", b"RIFF\x10\x00\x00\x00WEBP"])
def test_una_cabecera_buena_con_basura_detras_esta_danada(tmp_path, cabecera):
    ruta = _guardar(tmp_path, "rota.jpg", cabecera + bytes(range(256)) * 20)
    assert _mensaje(ruta) == "No se puede abrir esta foto: puede estar dañada."


# --- Nombres ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nombre, limpio",
    [
        ("bolsa_mesa.jpg", "bolsa_mesa"),
        ("../../etc/passwd", "passwd"),
        ("..\\..\\Windows\\system32\\foto.png", "foto"),
        ("C:\\Users\\alguien\\Mi Foto (1).JPG", "Mi_Foto_1"),
        ("/Users/alguien/Pictures/Café año 2026.webp", "Cafe_ano_2026"),
        ("foto.final.v2.jpeg", "fotofinalv2"),
        ("<script>alert(1)</script>.png", "script"),
        ("", "foto"),
        ("....jpg", "foto"),
        ("\u202egpj.exe", "gpj"),
        ("CON.jpg", "foto_CON"),
        ("  espacios   varios  .jpg", "espacios_varios"),
    ],
)
def test_el_nombre_se_limpia_sin_rutas(nombre, limpio):
    assert limpiar_nombre(nombre) == limpio


def test_el_nombre_limpio_es_corto_y_solo_tiene_caracteres_seguros():
    limpio = limpiar_nombre("ñandú " * 40 + ".jpg")
    assert 0 < len(limpio) <= 60
    assert limpio.replace("_", "").replace("-", "").isalnum() and limpio.isascii()


# --- Abrir la foto ------------------------------------------------------------------------------------------------


def test_la_foto_girada_por_la_camara_se_endereza(tmp_path):
    imagen = ayudas.imagen_foto(1200, 600)
    exif = Image.Exif()
    exif[0x0112] = 6  # la cámara la guardó tumbada
    memoria = io.BytesIO()
    imagen.save(memoria, "JPEG", exif=exif)
    ruta = _guardar(tmp_path, "girada.jpg", memoria.getvalue())
    valida = validar(ruta)
    assert (valida.ancho, valida.alto) == (600, 1200)
    assert abrir_normalizada(ruta).size == (600, 1200)


def test_una_foto_con_transparencia_se_abre_sobre_blanco(tmp_path):
    imagen = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    imagen.paste((200, 30, 30, 255), (200, 200, 600, 600))
    memoria = io.BytesIO()
    imagen.save(memoria, "PNG")
    abierta = abrir_normalizada(_guardar(tmp_path, "transparente.png", memoria.getvalue()))
    assert abierta.mode == "RGB"
    assert abierta.getpixel((10, 10)) == (255, 255, 255)
    assert abierta.getpixel((400, 400)) == (200, 30, 30)


def test_una_foto_con_perfil_de_color_se_abre_en_rgb(tmp_path):
    memoria = io.BytesIO()
    ayudas.imagen_foto(900, 900).save(memoria, "JPEG", icc_profile=subidas.perfil_srgb())
    abierta = abrir_normalizada(_guardar(tmp_path, "perfil.jpg", memoria.getvalue()))
    assert abierta.mode == "RGB" and abierta.size == (900, 900)


def test_los_limites_son_los_de_la_ficha():
    assert (subidas.MAX_FOTOS, subidas.MAX_MB, subidas.LADO_MINIMO, subidas.LADO_RECOMENDADO) == (20, 25, 500, 1000)


def test_un_archivo_con_nombre_de_clave_no_conserva_ese_nombre():
    """Si alguien sube un archivo llamado como su clave de OpenRouter, ese nombre no llega a ningún resultado."""
    from estudio.subidas import limpiar_nombre

    con_forma_de_clave = "sk-or-v1-" + "0123456789abcdef" * 2  # se arma aquí: en el código no hay nada con esa forma
    assert limpiar_nombre(f"{con_forma_de_clave}.jpg") == "foto"
    assert limpiar_nombre("mi clave SK-OR-v1-abcdef123456.png") == "foto"
    assert limpiar_nombre("skor_bolsa.jpg") == "skor_bolsa"
