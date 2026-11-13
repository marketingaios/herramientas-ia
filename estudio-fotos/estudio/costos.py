"""El gasto de las escenas con IA: modelos, costo estimado, tope de la sesión y `gastos.jsonl`."""

from __future__ import annotations

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
