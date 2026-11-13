"""Qué computador es y qué modelo de recorte le toca.

- Mac con chip Apple, o PC con tarjeta NVIDIA: el modelo completo («Calidad máxima»).
- Los demás: el modelo ligero («Modo rápido»), y la página lo dice.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

CALIDADES = ("automatica", "maxima", "rapida")
MODELO_COMPLETO = "birefnet-general"
MODELO_LIGERO = "birefnet-general-lite"

MENSAJE_MODO_RAPIDO = (
    "Modo rápido: tu computador no tiene aceleración y usamos un modelo más ligero. Puedes cambiarlo en Ajustes."
)
MENSAJE_NVIDIA_SIN_CUDA = (
    "La tarjeta NVIDIA no se pudo usar (pueden faltar CUDA o cuDNN): usamos el procesador, que es más lento. "
    "Puedes elegir «Rápida» en Ajustes."
)


@dataclass(frozen=True)
class Eleccion:
    modelo: str
    etiqueta: str  # «Calidad máxima» o «Modo rápido»
    nota: str | None = None  # lo que la página explica, si hace falta


def chip_apple() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def proveedores_disponibles() -> list[str]:
    """Los aceleradores que ofrece onnxruntime en este computador."""
    try:
        import onnxruntime

        return list(onnxruntime.get_available_providers())
    except Exception:
        return []


def tarjeta_nvidia() -> bool:
    """Hay tarjeta NVIDIA utilizable si se instaló la opción `gpu` y onnxruntime ofrece CUDA."""
    return "CUDAExecutionProvider" in proveedores_disponibles()


def elegir_modelo(calidad: str, *, apple: bool | None = None, nvidia: bool | None = None) -> Eleccion:
    """El modelo según el ajuste «Calidad del recorte» y, en Automática, según el computador."""
    if calidad == "maxima":
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    if calidad == "rapida":
        return Eleccion(MODELO_LIGERO, "Modo rápido")

    apple = chip_apple() if apple is None else apple
    if apple:
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    nvidia = tarjeta_nvidia() if nvidia is None else nvidia
    if nvidia:
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    return Eleccion(MODELO_LIGERO, "Modo rápido", MENSAJE_MODO_RAPIDO)


def proveedores_para(*, apple: bool | None = None, nvidia: bool | None = None) -> list:
    """Con qué se crea la sesión de recorte de entrada: el procesador, o CUDA si hay tarjeta NVIDIA.

    En un Mac se empieza siempre con el procesador; CoreML solo se usa si la medición dice que es más rápido.
    """
    apple = chip_apple() if apple is None else apple
    if apple:
        return ["CPUExecutionProvider"]
    nvidia = tarjeta_nvidia() if nvidia is None else nvidia
    if nvidia:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]
