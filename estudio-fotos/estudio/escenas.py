"""Escenas con IA: qué se le pide al modelo, la imagen de referencia y cómo se guarda lo que devuelve.

Cada escena guardada lleva en sus metadatos (XMP) la marca IPTC de imagen hecha con IA. Google Merchant Center la
exige y prohíbe quitarla: por eso todas las escenas se guardan con `guardar`, que la escribe siempre, también cuando
la escena cambia de medida.
"""

from __future__ import annotations

import io
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .encuadre import CALIDAD, SUBMUESTREO, codificar_jpeg, componer
from .plataformas import Plataforma
from .subidas import MAX_MEGAPIXELES, abrir_normalizada, detectar_tipo, perfil_srgb

FORMATOS = {"1:1": (1, 1), "4:5": (4, 5), "16:9": (16, 9)}

# Las 5 escenas preparadas (sirven a cualquier negocio). `pide` es lo que se le dice al modelo.
ESCENAS = [
    {
        "id": "mesa-madera",
        "nombre": "Mesa de madera clara con luz de mañana",
        "pide": "el producto sobre una mesa de madera clara, con la luz suave de la mañana entrando por un lado y el "
        "fondo desenfocado",
    },
    {
        "id": "cocina",
        "nombre": "Cocina moderna, encimera de piedra",
        "pide": "el producto sobre la encimera de piedra de una cocina moderna, con luz natural y la cocina "
        "desenfocada al fondo",
    },
    {
        "id": "colores-marca",
        "nombre": "Fondo liso con los colores de tu marca",
        "pide": "el producto sobre un fondo liso y limpio con los colores de la marca: el color principal es "
        "{color_principal} y el color de acento es {color_acento}; sin otros objetos alrededor",
    },
    {
        "id": "exterior",
        "nombre": "Exterior con luz natural suave",
        "pide": "el producto en un exterior con luz natural suave, sobre una superficie sencilla y con vegetación "
        "desenfocada al fondo",
    },
    {
        "id": "estudio",
        "nombre": "Estudio con sombra suave",
        "pide": "el producto en un estudio de fotografía, sobre un fondo neutro y liso, con una sombra suave debajo",
    },
]
PROPIA = "propia"  # la escena que escribe el usuario
PROPIA_MINIMO, PROPIA_MAXIMO = 3, 300

# El texto fijo de la petición (ficha, punto 4.4). Está en español, como todo: el usuario puede leer lo que se envía.
TEXTO_FIJO = (
    "Crea una fotografía publicitaria realista con el producto de la imagen de referencia. "
    "Usa exactamente ese producto: no cambies su etiqueta, su texto, su logo, su forma ni sus colores. "
    "No añadas textos, logos ni marcas de agua. "
    "El producto se ve entero, nítido y bien iluminado, apoyado de forma natural en la escena."
)

MARCA_IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
MARCA_PAGINA = "Para redes y fotos secundarias"
NOTA_PAGINA = "Mercado Libre, Amazon y Google piden fondo blanco en la foto principal."

MENSAJE_ESCENA = "Elige una de las escenas de la lista o escribe la tuya."
MENSAJE_FORMATO = "El formato debe ser 1:1, 4:5 o 16:9."
MENSAJE_PROPIA = f"Describe tu escena con entre {PROPIA_MINIMO} y {PROPIA_MAXIMO} caracteres."

# La imagen de referencia que se envía al modelo: el producto sobre blanco, 1024×1024, al 85 %.
_REFERENCIA = Plataforma(id="referencia", nombre="Referencia", ancho=1024, alto=1024, porcentaje=85)


class ErrorEscena(Exception):
    """La escena pedida no vale, o lo que devolvió el modelo no se puede guardar."""


@dataclass(frozen=True)
class Pedido:
    """Lo que el usuario eligió, ya comprobado."""

    escena: str  # id de la escena («propia» si la escribió el usuario)
    nombre: str  # como se muestra en la página
    formato: str
    texto: str  # el texto completo que se envía al modelo


@dataclass
class Escena:
    archivo: str
    ruta: Path
    ancho: int
    alto: int
    peso: int
    escena: str
    nombre_escena: str
    formato: str
    modelo: str
    costo: float | None  # el costo real; None si OpenRouter no lo informó
    costo_estimado: float
    aviso: str | None = None


def escenas_publicas() -> list[dict]:
    return [{"id": escena["id"], "nombre": escena["nombre"]} for escena in ESCENAS]


def preparar_pedido(escena: object, formato: object, propia: object, negocio: dict) -> Pedido:
    """Comprueba la escena y el formato elegidos y escribe el texto de la petición."""
    if not isinstance(formato, str) or formato not in FORMATOS:
        raise ErrorEscena(MENSAJE_FORMATO)
    if escena == PROPIA:
        descripcion = _limpiar_propia(propia)
        return Pedido(PROPIA, descripcion, formato, f"{TEXTO_FIJO} La escena: {descripcion}")
    for preparada in ESCENAS:
        if preparada["id"] == escena:
            pide = preparada["pide"].format(
                color_principal=negocio["color_principal"], color_acento=negocio["color_acento"]
            )
            return Pedido(preparada["id"], preparada["nombre"], formato, f"{TEXTO_FIJO} La escena: {pide}.")
    raise ErrorEscena(MENSAJE_ESCENA)


def _limpiar_propia(valor: object) -> str:
    if not isinstance(valor, str):
        raise ErrorEscena(MENSAJE_PROPIA)
    limpio = "".join(c if unicodedata.category(c)[0] != "C" else " " for c in valor)  # fuera caracteres de control
    limpio = " ".join(limpio.split())
    if not PROPIA_MINIMO <= len(limpio) <= PROPIA_MAXIMO:
        raise ErrorEscena(MENSAJE_PROPIA)
    return limpio


def imagen_referencia(recorte: Image.Image) -> bytes:
    """El producto sobre fondo blanco (1024×1024, al 85 %, JPEG calidad 90): lo que el modelo debe respetar."""
    imagen, encuadre = componer(recorte, _REFERENCIA)
    datos, _calidad, _cabe, _blanco = codificar_jpeg(imagen, encuadre, None)
    return datos


# --- Guardar lo que devuelve el modelo ---------------------------------------------------------------------------------


def paquete_xmp() -> bytes:
    """Los metadatos XMP con la marca IPTC de imagen hecha con IA (`Iptc4xmpExt:DigitalSourceType`)."""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about="" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">\n'
        f"   <Iptc4xmpExt:DigitalSourceType>{MARCA_IPTC}</Iptc4xmpExt:DigitalSourceType>\n"
        "  </rdf:Description>\n"
        " </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


def tiene_marca(datos: bytes) -> bool:
    """¿Este JPEG lleva la marca IPTC de imagen hecha con IA en su XMP?"""
    try:
        with Image.open(io.BytesIO(datos)) as imagen:
            xmp = imagen.info.get("xmp", b"")
    except Exception:
        return False
    if isinstance(xmp, str):
        xmp = xmp.encode("utf-8")
    return f"<Iptc4xmpExt:DigitalSourceType>{MARCA_IPTC}</Iptc4xmpExt:DigitalSourceType>".encode() in xmp


def medida_exacta(ancho: int, alto: int, formato: str) -> tuple[int, int]:
    """La medida más grande con la proporción exacta del formato que cabe en ancho×alto (sin ampliar nada)."""
    a, b = FORMATOS[formato]
    unidad = min(ancho // a, alto // b)
    if unidad < 1:
        raise ErrorEscena("La imagen que devolvió el modelo es demasiado pequeña.")
    return a * unidad, b * unidad


def ajustar_formato(imagen: Image.Image, formato: str) -> tuple[Image.Image, str | None]:
    """Deja la escena con la proporción exacta: recorta centrada lo mínimo; no amplía ni deforma.

    Devuelve también un aviso si hubo que recortar bastante (el modelo devolvió otro formato).
    """
    ancho, alto = medida_exacta(imagen.width, imagen.height, formato)
    aviso = None
    if ancho < imagen.width * 0.95 or alto < imagen.height * 0.95:
        aviso = f"el modelo devolvió otra proporción y se recortó a {formato}: revisa que el producto se vea entero"
    if (ancho, alto) == imagen.size:
        return imagen, aviso
    izquierda, arriba = (imagen.width - ancho) // 2, (imagen.height - alto) // 2
    return imagen.crop((izquierda, arriba, izquierda + ancho, arriba + alto)), aviso


def codificar(imagen: Image.Image) -> bytes:
    """JPEG en sRGB, calidad 90, siempre con la marca IPTC de imagen hecha con IA."""
    memoria = io.BytesIO()
    limpia = imagen.convert("RGB")
    limpia.info = {}  # ningún metadato de lo que devolvió el modelo (comentarios, EXIF…): solo el perfil y la marca
    limpia.save(
        memoria, "JPEG", quality=CALIDAD, subsampling=SUBMUESTREO, optimize=True,
        icc_profile=perfil_srgb(), xmp=paquete_xmp(),
    )
    datos = memoria.getvalue()
    if not tiene_marca(datos):
        raise ErrorEscena("No se pudo escribir la marca de imagen hecha con IA.")
    return datos


def cambiar_medida(datos: bytes, ancho: int, alto: int) -> bytes:
    """Una escena ya guardada, en otra medida: la marca IPTC se conserva."""
    with Image.open(io.BytesIO(datos)) as imagen:
        imagen.load()
        reducida = imagen.convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)
    return codificar(reducida)


def guardar(
    datos: bytes,
    pedido: Pedido,
    foto: str,
    carpeta: Path,
    *,
    modelo: str,
    costo: float | None,
    costo_estimado: float,
) -> Escena:
    """Guarda la imagen que devolvió el modelo como `<foto>_escena_<escena>_<ancho>x<alto>.jpg`, con la marca IPTC."""
    if detectar_tipo(datos[:32]) not in ("jpeg", "png", "webp"):
        raise ErrorEscena("El modelo no devolvió una imagen.")
    try:
        with Image.open(io.BytesIO(datos)) as cabecera:
            if cabecera.width * cabecera.height > MAX_MEGAPIXELES * 1_000_000:
                raise ErrorEscena("La imagen que devolvió el modelo es demasiado grande.")
        imagen = abrir_normalizada(io.BytesIO(datos))
    except ErrorEscena:
        raise
    except Exception:
        raise ErrorEscena("La imagen que devolvió el modelo no se puede abrir.") from None

    imagen, aviso = ajustar_formato(imagen, pedido.formato)
    codificada = codificar(imagen)

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    # Cada escena costó dinero: una nueva nunca pisa otra con el mismo nombre.
    numero, sufijo = 1, ""
    while True:
        archivo = f"{foto}_escena_{pedido.escena}{sufijo}_{imagen.width}x{imagen.height}.jpg"
        ruta = carpeta / archivo
        if not ruta.exists():
            break
        numero += 1
        sufijo = f"-{numero}"
    temporal = ruta.with_name(f"{ruta.name}.tmp-{os.getpid()}")
    temporal.write_bytes(codificada)
    os.replace(temporal, ruta)
    return Escena(
        archivo=archivo, ruta=ruta, ancho=imagen.width, alto=imagen.height, peso=len(codificada),
        escena=pedido.escena, nombre_escena=pedido.nombre, formato=pedido.formato, modelo=modelo,
        costo=costo, costo_estimado=costo_estimado, aviso=aviso,
    )
