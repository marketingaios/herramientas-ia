"""El gasto de las escenas con IA: modelos, costo estimado, tope de la sesión y `gastos.jsonl`."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Los modelos de escenas, con su id en OpenRouter y el costo de partida por imagen de 1K (ficha, punto 4.4).
# El costo de partida se corrige con los costos reales anotados en gastos.jsonl.
MODELOS_ESCENAS = [
    {"id": "google/gemini-nano-banana-2.1", "nombre": "Nano Banana 2.1", "costo_partida_usd": 0.04, "recomendado": True},
    {"id": "google/gemini-3.1-flash-lite-image", "nombre": "Nano Banana 2 Lite", "costo_partida_usd": 0.04, "recomendado": False},
    {"id": "google/gemini-3.1-flash-image", "nombre": "Nano Banana 2", "costo_partida_usd": 0.07, "recomendado": False},
    {"id": "google/gemini-3-pro-image", "nombre": "Nano Banana Pro", "costo_partida_usd": 0.14, "recomendado": False},
]
MODELO_POR_DEFECTO = "google/gemini-nano-banana-2.1"
TOPE_POR_DEFECTO_USD = 1.0
TOPE_MAXIMO_USD = 1000.0

IDS_MODELOS = {modelo["id"] for modelo in MODELOS_ESCENAS}


def dolares(importe: float) -> str:
    """Un importe como se lee en español: «0,20 $». Con tres decimales solo si hacen falta («0,038 $»)."""
    if abs(importe) < 0.0995 and round(importe, 3) != round(importe, 2):
        return f"{importe:.3f}".replace(".", ",") + " $"
    return f"{importe:.2f}".replace(".", ",") + " $"


def modelos_publicos() -> list[dict]:
    """La lista de modelos para la página de Ajustes."""
    return [
        {
            "id": modelo["id"],
            "nombre": modelo["nombre"] + (" (recomendado)" if modelo["recomendado"] else ""),
            "costo_partida": dolares(modelo["costo_partida_usd"]),
        }
        for modelo in MODELOS_ESCENAS
    ]


# --- Estimación ------------------------------------------------------------------------------------------------------

# Un margen mínimo para comparar importes: 0,2 + 0,8 no puede «superar» 1 por un redondeo del procesador.
_MARGEN = 1e-9


def costo_partida(modelo: str) -> float:
    for datos in MODELOS_ESCENAS:
        if datos["id"] == modelo:
            return datos["costo_partida_usd"]
    raise ValueError("modelo de escenas desconocido")


def leer_gastos(ruta: Path) -> list[dict]:
    """Las líneas de `gastos.jsonl`. Una línea rota (o editada a mano) se salta: no estropea la estimación."""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    gastos = []
    for linea in texto.splitlines():
        try:
            gasto = json.loads(linea)
        except ValueError:
            continue
        if isinstance(gasto, dict):
            gastos.append(gasto)
    return gastos


def _es_importe(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor == valor and 0 <= valor < 1e6


def costo_medio(gastos: list[dict], modelo: str) -> float | None:
    """La media de los costos reales por imagen de un modelo, o None si todavía no hay ninguna escena hecha."""
    total, imagenes = 0.0, 0
    for gasto in gastos:
        cuantas = gasto.get("imagenes")
        if gasto.get("modelo") != modelo or not _es_importe(gasto.get("costo_usd")):
            continue
        if isinstance(cuantas, bool) or not isinstance(cuantas, int) or cuantas < 1:
            continue
        total += gasto["costo_usd"]
        imagenes += cuantas
    return total / imagenes if imagenes else None


@dataclass(frozen=True)
class Estimacion:
    modelo: str
    imagenes: int
    por_imagen: float
    total: float
    origen: str  # «partida» (el costo de partida del modelo) o «media» (la media de los costos reales)

    def texto(self) -> str:
        """Lo que la página pregunta antes de gastar: «5 escenas · costo estimado 0,20 $ · ¿Generar?»."""
        escenas = "1 escena" if self.imagenes == 1 else f"{self.imagenes} escenas"
        return f"{escenas} · costo estimado {dolares(self.total)} · ¿Generar?"


def estimar(ruta_gastos: Path, modelo: str, imagenes: int) -> Estimacion:
    """El costo estimado: el de partida del modelo y, en cuanto hay escenas hechas, la media de sus costos reales."""
    partida = costo_partida(modelo)
    media = costo_medio(leer_gastos(ruta_gastos), modelo)
    por_imagen = partida if media is None else media
    return Estimacion(
        modelo=modelo,
        imagenes=imagenes,
        por_imagen=round(por_imagen, 6),
        total=round(por_imagen * imagenes, 6),
        origen="partida" if media is None else "media",
    )


# --- Tope de la sesión y límite de la clave ------------------------------------------------------------------------------


class SinPresupuesto(Exception):
    """La estimación no cabe en lo que queda: no se gasta. `motivo` es «tope» (la sesión) o «clave» (OpenRouter)."""

    def __init__(self, mensaje: str, motivo: str) -> None:
        super().__init__(mensaje)
        self.motivo = motivo


def mensaje_tope(costaria: float, quedan: float) -> str:
    return (
        f"Esto costaría {dolares(costaria)} y en esta sesión te quedan {dolares(max(0.0, quedan))}. "
        "Sube el tope en Ajustes o genera menos escenas."
    )


def mensaje_clave(costaria: float, quedan: float) -> str:
    return (
        f"Esto costaría {dolares(costaria)} y a tu clave de OpenRouter le quedan {dolares(max(0.0, quedan))}. "
        "Sube el límite de la clave en OpenRouter o genera menos escenas."
    )


def comprobar_tope(costaria: float, tope: float, gastado: float) -> None:
    """Si la estimación supera lo que queda del tope de la sesión, no se gasta."""
    quedan = tope - gastado
    if costaria > quedan + _MARGEN:
        raise SinPresupuesto(mensaje_tope(costaria, quedan), "tope")


def comprobar_clave(costaria: float, restante: float | None) -> None:
    """Si la estimación supera lo que queda en la clave, no se gasta. Una clave sin límite (None) pasa."""
    if restante is not None and costaria > restante + _MARGEN:
        raise SinPresupuesto(mensaje_clave(costaria, restante), "clave")


def antes_de_gastar(costaria: float, tope: float, gastado: float, probar: Callable[[], object]) -> None:
    """Las dos comprobaciones, en orden: primero el tope local y solo después se pregunta a OpenRouter por la clave.

    Con el tope superado no se llama a OpenRouter. `probar` es `Cliente.probar` (consulta `/key`, no gasta).
    """
    comprobar_tope(costaria, tope, gastado)
    estado = probar()
    comprobar_clave(costaria, getattr(estado, "restante", None))


# --- gastos.jsonl ----------------------------------------------------------------------------------------------------


def anotar_gasto(
    ruta: Path,
    modelo: str,
    costo_estimado: float,
    costo_real: float | None,
    *,
    imagenes: int = 1,
    ahora: datetime | None = None,
) -> dict:
    """Añade una línea a `gastos.jsonl`. Solo estos cinco campos: nunca la clave, ni nombres de fotos, ni textos."""
    momento = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    gasto = {
        "ts": momento.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modelo": modelo,
        "imagenes": imagenes,
        "costo_estimado_usd": round(costo_estimado, 6),
        "costo_usd": None if costo_real is None else round(costo_real, 6),
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8", newline="\n") as archivo:
        archivo.write(json.dumps(gasto, ensure_ascii=False) + "\n")
        archivo.flush()
        os.fsync(archivo.fileno())
    return gasto
