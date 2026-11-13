"""Quitar el fondo en el computador, con rembg y BiRefNet (licencia MIT).

El modelo se pide SIEMPRE por su nombre: `birefnet-general` o `birefnet-general-lite`. Sin nombre, rembg usaría
`bria-rmbg`, cuya licencia no permite el uso comercial; por eso la única puerta a rembg es `crear_sesion`.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .encuadre import UMBRAL_PRODUCTO, caja_producto
from .equipo import PROCESADOR

# Los dos únicos modelos que usa la herramienta, con su tamaño de descarga en MB.
MODELOS = {
    "birefnet-general": {"etiqueta": "Calidad máxima", "mb": 973},
    "birefnet-general-lite": {"etiqueta": "Modo rápido", "mb": 224},
}
MODELO_PROHIBIDO = "bria-rmbg"  # licencia no comercial: nunca se usa

COBERTURA_MINIMA = 0.05  # con menos del 5 % o más del 95 % de la foto, no hay «un producto claro»
COBERTURA_MAXIMA = 0.95
MEGAPIXELES_LIMPIEZA_COLOR = 16  # por encima, limpiar el color del borde pide demasiada memoria

MENSAJE_SIN_PRODUCTO = (
    "No encontramos un producto claro en esta foto. Prueba con el producto más grande y un fondo más simple."
)
MENSAJE_DESCARGA_FALLIDA = "No se pudo descargar el modelo de recorte. Revisa tu conexión y vuelve a intentarlo."
MENSAJE_DESCARGANDO = "Descargando el modelo de recorte, solo la primera vez…"


def mensaje_descarga(modelo: str) -> str:
    return f"Descargando el modelo de recorte ({MODELOS[modelo]['mb']} MB), solo la primera vez"


class ErrorRecorte(Exception):
    """El recorte no se pudo hacer; el mensaje es para el usuario."""


class SinProducto(ErrorRecorte):
    def __init__(self) -> None:
        super().__init__(MENSAJE_SIN_PRODUCTO)


class DescargaFallida(ErrorRecorte):
    def __init__(self) -> None:
        super().__init__(MENSAJE_DESCARGA_FALLIDA)


@dataclass
class Recorte:
    imagen: Image.Image  # RGBA, del tamaño de la foto original
    cobertura: float  # parte de la foto que ocupa el producto (0 a 1)
    caja: tuple[int, int, int, int]
    segundos_modelo: float


# --- La máscara ---------------------------------------------------------------------------------------------------


def limpiar_mascara(mascara: np.ndarray) -> np.ndarray:
    """Limpieza mínima: anula la neblina (alfa por debajo del 5 %) y estira el resto hasta 255.

    No erosiona ni mueve los bordes: un alfa del 50 % sigue en el 50 %. Sin esto, la neblina que el modelo deja
    repartida por el fondo mancharía el blanco puro.
    """
    suave = (mascara.astype(np.float32) - UMBRAL_PRODUCTO) * (255.0 / (255 - 2 * UMBRAL_PRODUCTO))
    return np.clip(np.rint(suave), 0, 255).astype(np.uint8)


def cobertura(alfa: np.ndarray) -> float:
    """La parte de la foto que es producto (alfa de la mitad para arriba)."""
    return float((alfa >= 128).mean())


def color_del_producto(imagen: Image.Image, alfa: np.ndarray) -> np.ndarray:
    """El color del producto sin la mezcla del fondo original en los bordes.

    Un píxel del borde es una mezcla del producto y del fondo de la foto; al ponerlo sobre blanco quedaría una línea
    del color del fondo viejo. Aquí se estima el color propio del producto (con pymatting, como hace rembg).
    """
    color = np.asarray(imagen.convert("RGB"))
    if imagen.width * imagen.height > MEGAPIXELES_LIMPIEZA_COLOR * 1_000_000:
        return color
    try:
        from pymatting.foreground.estimate_foreground_ml import estimate_foreground_ml

        estimado = estimate_foreground_ml(
            color.astype(np.float32) / np.float32(255), alfa.astype(np.float32) / np.float32(255)
        )
        return np.clip(np.rint(estimado * 255), 0, 255).astype(np.uint8)
    except Exception:
        return color  # sin la limpieza de color el recorte sigue siendo válido


def recortar(imagen: Image.Image, recortador: "Recortador") -> Recorte:
    """Quita el fondo de una foto ya abierta (RGB). Lanza `SinProducto` si no hay un producto claro."""
    inicio = time.perf_counter()
    mascara = recortador.mascara(imagen)
    segundos = time.perf_counter() - inicio

    if mascara.size != imagen.size:
        mascara = mascara.resize(imagen.size, Image.Resampling.LANCZOS)
    alfa = limpiar_mascara(np.asarray(mascara.convert("L")))
    parte = cobertura(alfa)
    caja = caja_producto(alfa)
    if caja is None or not COBERTURA_MINIMA <= parte <= COBERTURA_MAXIMA:
        raise SinProducto()

    color = color_del_producto(imagen, alfa)
    recorte = Image.fromarray(np.dstack([color, alfa]), "RGBA")
    return Recorte(imagen=recorte, cobertura=parte, caja=caja, segundos_modelo=segundos)


# --- Los recortadores ---------------------------------------------------------------------------------------------


class Recortador:
    """Lo que la cola necesita de un recortador."""

    modelo: str = ""
    acelerador_fallido = False  # se pidió un acelerador, falló y el recortador siguió con el procesador

    def descargado(self) -> bool:
        return True

    def descargar(self, avance: Callable[[int], None] | None = None) -> None:
        """Descarga el modelo si falta; `avance` recibe los bytes ya bajados."""

    def preparar(self) -> None:
        """Deja el recortador listo para usar (carga el modelo en memoria una sola vez)."""

    def mascara(self, imagen: Image.Image) -> Image.Image:
        raise NotImplementedError

    def proveedores_activos(self) -> list[str]:
        return []

    def acelerado(self) -> bool:
        """Si trabaja con un acelerador (CoreML o CUDA) y no con el procesador."""
        return False


class RecortadorSimulado(Recortador):
    """Para las pruebas: «recorta» un óvalo en el centro, sin modelo y sin internet."""

    modelo = "simulado"

    def __init__(self) -> None:
        self.preparado = 0
        self.fotos = 0

    def preparar(self) -> None:
        self.preparado += 1

    def mascara(self, imagen: Image.Image) -> Image.Image:
        self.fotos += 1
        ancho, alto = imagen.size
        mascara = Image.new("L", (ancho, alto), 0)
        ImageDraw.Draw(mascara).ellipse(
            (round(ancho * 0.22), round(alto * 0.14), round(ancho * 0.78), round(alto * 0.86)), fill=255
        )
        return mascara.filter(ImageFilter.GaussianBlur(1.2))


def preparar_entorno(carpeta_modelos: Path) -> None:
    """Dice a rembg dónde guardar los modelos: en `herramientas-ia/modelos/`.

    Comprobado en el código de rembg 2.0.87: `REMBG_HOME` es la raíz (cada modelo queda en
    `<REMBG_HOME>/models/<nombre>/<nombre>.onnx`), pero si existe `U2NET_HOME` gana esa. Ponemos las dos, para que
    nada se lea ni se escriba en la carpeta personal.
    """
    carpeta = str(Path(carpeta_modelos).resolve())
    os.environ["REMBG_HOME"] = carpeta
    os.environ["U2NET_HOME"] = carpeta


def ruta_modelo(carpeta_modelos: Path, modelo: str) -> Path:
    return Path(carpeta_modelos) / "models" / modelo / f"{modelo}.onnx"


def comprobar_modelo(modelo: object) -> str:
    """Solo se admiten los dos modelos BiRefNet de la herramienta, siempre por su nombre."""
    if not isinstance(modelo, str) or modelo not in MODELOS or modelo == MODELO_PROHIBIDO:
        raise ValueError("El modelo de recorte debe ser «birefnet-general» o «birefnet-general-lite».")
    return modelo


def crear_sesion(modelo: str, carpeta_modelos: Path, proveedores: list | None = None):
    """La única puerta a rembg: crea la sesión con el nombre del modelo siempre explícito."""
    modelo = comprobar_modelo(modelo)
    preparar_entorno(carpeta_modelos)
    import rembg

    return rembg.new_session(modelo, providers=list(proveedores or PROCESADOR))


class RecortadorRembg(Recortador):
    """El recortador de verdad: BiRefNet con rembg y onnxruntime."""

    def __init__(self, modelo: str, carpeta_modelos: Path, proveedores: list | None = None) -> None:
        self.modelo = comprobar_modelo(modelo)
        self.carpeta_modelos = Path(carpeta_modelos)
        self.proveedores = list(proveedores or PROCESADOR)
        self.pedidos = list(self.proveedores)  # lo que se pidió al crearlo, aunque después se vuelva al procesador
        self._sesion = None

    @property
    def archivo(self) -> Path:
        return ruta_modelo(self.carpeta_modelos, self.modelo)

    def descargado(self) -> bool:
        return self.archivo.is_file()

    def descargar(self, avance: Callable[[int], None] | None = None) -> None:
        if self.descargado():
            return
        preparar_entorno(self.carpeta_modelos)
        carpeta = self.archivo.parent
        carpeta.mkdir(parents=True, exist_ok=True)
        for resto in carpeta.glob("tmp*"):  # una descarga anterior que se cortó
            if resto.is_file():
                resto.unlink(missing_ok=True)

        parar = threading.Event()

        def vigilar() -> None:
            while not parar.wait(0.5):
                if avance:
                    avance(_bytes_en(carpeta))

        vigilante = threading.Thread(target=vigilar, name="avance-descarga", daemon=True)
        vigilante.start()
        try:
            from rembg.sessions import sessions_class

            clase = next(c for c in sessions_class if c.name() == self.modelo)
            clase.download_models()
        except Exception:
            raise DescargaFallida() from None
        finally:
            parar.set()
            vigilante.join(timeout=2)
        if not self.descargado():
            raise DescargaFallida()

    def acelerado(self) -> bool:
        return self.proveedores != PROCESADOR

    def _volver_al_procesador(self) -> None:
        """El acelerador falló: se sigue con el procesador, sin romper el lote."""
        self.acelerador_fallido = True
        self.proveedores = list(PROCESADOR)
        self._sesion = None
        self._sesion = crear_sesion(self.modelo, self.carpeta_modelos, self.proveedores)

    def preparar(self) -> None:
        if self._sesion is not None:
            return
        try:
            self._sesion = crear_sesion(self.modelo, self.carpeta_modelos, self.proveedores)
        except Exception:
            if not self.acelerado():
                raise
            self._volver_al_procesador()

    def mascara(self, imagen: Image.Image) -> Image.Image:
        self.preparar()
        foto = imagen.convert("RGB")
        try:
            return self._sesion.predict(foto)[0]
        except Exception:
            if not self.acelerado():
                raise
            self._volver_al_procesador()
            return self._sesion.predict(foto)[0]

    def proveedores_activos(self) -> list[str]:
        if self._sesion is None:
            return []
        return list(self._sesion.inner_session.get_providers())


def _bytes_en(carpeta: Path) -> int:
    total = 0
    try:
        for archivo in carpeta.iterdir():
            try:
                total += archivo.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total
