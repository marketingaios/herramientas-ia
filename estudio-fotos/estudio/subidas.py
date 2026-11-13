"""Comprueba cada foto que se sube: tipo por contenido, peso, píxeles, lado corto y nombre limpio."""

from __future__ import annotations

import io
import math
import re
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

MAX_FOTOS = 20
MAX_MB = 25
MAX_BYTES = MAX_MB * 1024 * 1024
LADO_MINIMO = 500
LADO_RECOMENDADO = 1000
MAX_MEGAPIXELES = 50

# Segunda barrera contra las «bombas de descompresión»: Pillow se niega a abrir más del doble de este tope.
Image.MAX_IMAGE_PIXELS = MAX_MEGAPIXELES * 1_000_000

MENSAJE_FORMATO = "Este archivo no es una foto JPG, PNG o WEBP."
MENSAJE_HEIC = (
    "Es una foto HEIC (iPhone). Expórtala como JPG, o en el iPhone ve a Ajustes › Cámara › Formatos "
    "y elige «Más compatible»."
)
MENSAJE_DANADA = "No se puede abrir esta foto: puede estar dañada."
MENSAJE_DEMASIADAS = f"Se pueden subir hasta {MAX_FOTOS} fotos a la vez."

_FORMATOS_PILLOW = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
_MARCAS_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"heif"}
_RESERVADOS_WINDOWS = {"con", "prn", "aux", "nul"} | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)}


class ErrorFoto(Exception):
    """La foto no se acepta; el mensaje dice qué pasó y qué hacer."""


@dataclass(frozen=True)
class FotoValida:
    tipo: str  # jpeg, png o webp
    ancho: int
    alto: int
    aviso: str | None


def numero(valor: float, decimales: int = 1) -> str:
    """Un número con coma decimal, como se escribe en español."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def detectar_tipo(cabecera: bytes) -> str | None:
    """El tipo real del archivo, por sus primeros bytes (no por el nombre)."""
    if cabecera.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "webp"
    if cabecera[4:8] == b"ftyp" and cabecera[8:12] in _MARCAS_HEIC:
        return "heic"
    return None


def limpiar_nombre(nombre: str) -> str:
    """El nombre de la foto sin ruta, sin extensión y solo con letras, números, guiones y guiones bajos."""
    base = re.split(r"[\\/]", nombre or "")[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = unicodedata.normalize("NFKD", base)
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = base.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"\s+", "_", base.strip())
    base = re.sub(r"[^A-Za-z0-9_-]", "", base)
    base = re.sub(r"_{2,}", "_", base).strip("_-")[:60].strip("_-")
    if not base or base.lower() in _RESERVADOS_WINDOWS:
        base = f"foto_{base}".strip("_") if base else "foto"
    return base


def validar(ruta: Path, peso: int | None = None) -> FotoValida:
    """Comprueba una foto ya guardada en disco. Lanza `ErrorFoto` con el mensaje para el usuario."""
    ruta = Path(ruta)
    peso = ruta.stat().st_size if peso is None else peso
    if peso > MAX_BYTES:
        megas = math.ceil(peso / (1024 * 1024) * 10) / 10  # hacia arriba: nunca «pesa 25,0 MB: el máximo es 25»
        raise ErrorFoto(f"La foto pesa {numero(megas)} MB: el máximo es {MAX_MB}.")

    with ruta.open("rb") as archivo:
        tipo = detectar_tipo(archivo.read(32))
    if tipo == "heic":
        raise ErrorFoto(MENSAJE_HEIC)
    if tipo is None:
        raise ErrorFoto(MENSAJE_FORMATO)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(ruta, formats=[_FORMATOS_PILLOW[tipo]]) as imagen:
                ancho, alto = imagen.size
                megapixeles = ancho * alto / 1_000_000
                if megapixeles > MAX_MEGAPIXELES:
                    raise ErrorFoto(_mensaje_megapixeles(f"{megapixeles:.0f}"))
                orientacion = imagen.getexif().get(0x0112, 1)
                imagen.load()  # decodifica entera: así se detecta una foto cortada o dañada
    except ErrorFoto:
        raise
    except Image.DecompressionBombError:
        raise ErrorFoto(_mensaje_megapixeles(f"más de {MAX_MEGAPIXELES * 2}"))
    except Exception:
        raise ErrorFoto(MENSAJE_DANADA)

    if orientacion in (5, 6, 7, 8):  # la cámara guardó la foto girada
        ancho, alto = alto, ancho

    lado_corto = min(ancho, alto)
    if lado_corto < LADO_MINIMO:
        raise ErrorFoto(f"La foto mide {lado_corto} px de lado corto: se necesitan al menos {LADO_MINIMO}.")
    aviso = None
    if lado_corto < LADO_RECOMENDADO:
        aviso = f"La foto mide {lado_corto} px de lado corto: con 1.000 o más se verá mejor."
    return FotoValida(tipo=tipo, ancho=ancho, alto=alto, aviso=aviso)


def _mensaje_megapixeles(cuantos: str) -> str:
    return f"La foto mide {cuantos} megapíxeles: el máximo es {MAX_MEGAPIXELES}. Redúcela y vuelve a subirla."


_SRGB = None


def perfil_srgb() -> bytes:
    """El perfil de color sRGB que llevan los JPEG que se exportan."""
    global _SRGB
    if _SRGB is None:
        _SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    return _SRGB


def abrir_normalizada(ruta: Path) -> Image.Image:
    """Abre una foto ya validada: derecha (orientación EXIF), en sRGB y sin transparencia (sobre blanco)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with Image.open(ruta) as original:
            original.load()
            imagen = ImageOps.exif_transpose(original) or original
            imagen = _a_srgb(imagen)

    if imagen.mode in ("RGBA", "LA", "PA") or (imagen.mode == "P" and "transparency" in imagen.info):
        imagen = imagen.convert("RGBA")
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        return fondo
    return imagen.convert("RGB")


def _a_srgb(imagen: Image.Image) -> Image.Image:
    """Convierte a sRGB las fotos con otro perfil de color (por ejemplo Display P3 del iPhone)."""
    perfil = imagen.info.get("icc_profile")
    if not perfil or imagen.mode not in ("RGB", "RGBA"):
        return imagen
    try:
        origen = ImageCms.ImageCmsProfile(io.BytesIO(perfil))
        destino = ImageCms.createProfile("sRGB")
        return ImageCms.profileToProfile(imagen, origen, destino, outputMode=imagen.mode)
    except Exception:
        return imagen  # un perfil raro no debe impedir trabajar con la foto
