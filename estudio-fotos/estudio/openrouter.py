"""Cliente de OpenRouter: la única conexión a internet de la herramienta en uso normal.

Solo se llama cuando el usuario confirma un gasto (`generar`) o pulsa Probar (`probar`). Los errores se deciden por
el código HTTP y por campos estructurados (`error.metadata.limit_source`, `reason`, `code`, `type`), nunca por el
texto del mensaje. La clave se lee del `.env` en cada llamada y no aparece en ningún mensaje.
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

from .costos import dolares
from .subidas import detectar_tipo

MENSAJES = {
    "sin_clave": "Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes.",
    "clave": "OpenRouter no acepta esta clave. Revísala en Ajustes.",
    "saldo": "Se acabó el saldo o el límite de tu clave de OpenRouter.",
    "espera_agotada": "OpenRouter sigue pidiendo esperar. Prueba de nuevo en unos minutos.",
    "generacion": "La escena no se pudo generar y no se cobró. Inténtalo otra vez.",
    "proveedor": "El modelo no está disponible ahora. Prueba en unos minutos o elige otro en Ajustes.",
    "foto": "El modelo no aceptó esta foto. Prueba con otra o con una más pequeña.",
    "filtro": "El modelo no quiso generar esta escena. Prueba con otra descripción.",
    "conexion": "Sin conexión a internet: el recorte sigue funcionando, las escenas con IA no.",
    "tiempo": "OpenRouter no respondió a tiempo. Antes de repetir, mira en openrouter.ai si se cobró.",
}

# Los errores que afectan a todo el lote: no tiene sentido seguir con la foto siguiente.
DETIENEN_EL_LOTE = {"sin_clave", "clave", "saldo", "espera", "proveedor", "conexion", "tiempo", "otro"}

FUENTES_DE_SALDO = {"openrouter_key_limit", "openrouter_credits"}
REINTENTOS = 3
ESPERA_POR_DEFECTO = 5
ESPERA_MAXIMA = 60


def mensaje_espera(segundos: int) -> str:
    return f"OpenRouter pide esperar un momento. Lo intentamos de nuevo en {segundos} s."


def mensaje_otro(codigo: int) -> str:
    return f"OpenRouter respondió con un error (código {codigo}). Inténtalo otra vez en unos minutos."


class ErrorOpenRouter(Exception):
    """Algo falló con OpenRouter. `tipo` dice qué; el mensaje es para el usuario y nunca lleva la clave."""

    def __init__(self, tipo: str, mensaje: str | None = None, *, posible_cobro: bool = False) -> None:
        super().__init__(mensaje or MENSAJES[tipo])
        self.tipo = tipo
        self.posible_cobro = posible_cobro  # la petición salió y no sabemos si se cobró (tiempo agotado)

    @property
    def detiene_el_lote(self) -> bool:
        return self.tipo in DETIENEN_EL_LOTE


@dataclass(frozen=True)
class EstadoClave:
    limite: float | None  # None: la clave no tiene límite
    restante: float | None
    usado: float | None

    def texto(self) -> str:
        limite = "sin límite" if self.limite is None else f"límite {dolares(self.limite)}"
        return f"Conexión correcta · {limite} · usado {dolares(self.usado or 0.0)}"


@dataclass(frozen=True)
class Imagen:
    datos: bytes
    costo: float | None  # el costo real (`usage.cost`), o None si OpenRouter no lo informó


def clasificar(codigo: int, cuerpo: object) -> str:
    """Qué significa una respuesta de error: el tipo de error, o «reintentar» si hay que esperar y repetir."""
    error = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    error = error if isinstance(error, dict) else {}
    metadatos = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    fuente = metadatos.get("limit_source")
    motivo = metadatos.get("reason", error.get("reason"))
    # Valores de campos estructurados (nunca el texto libre de `message`).
    etiquetas = {valor for valor in (error.get("code"), error.get("type"), *metadatos.values()) if isinstance(valor, str)}

    if codigo == 401:
        return "clave"
    if codigo in (402, 403) and fuente in FUENTES_DE_SALDO:
        return "saldo"
    if codigo == 402:
        if fuente == "openrouter_in_flight_budget":
            # Con «weight_exceeds_budget» reintentar no sirve: el presupuesto no alcanza para esta petición.
            return "saldo" if motivo == "weight_exceeds_budget" else "reintentar"
        return "saldo"
    if codigo == 403:
        return "filtro" if "content_policy_violation" in etiquetas else "otro"
    if codigo == 429:
        return "reintentar"
    if codigo == 400:
        return "foto"
    if codigo == 502:
        return "generacion"
    if codigo == 503:
        return "proveedor"
    return "otro"


def _espera(cabeceras: httpx.Headers) -> int:
    """Los segundos que pide `Retry-After` (5 si no viene; 60 como máximo)."""
    try:
        segundos = float(cabeceras.get("retry-after", ""))
    except ValueError:
        segundos = ESPERA_POR_DEFECTO
    if not segundos > 0:
        segundos = ESPERA_POR_DEFECTO
    return int(min(ESPERA_MAXIMA, max(1, round(segundos))))


class Cliente:
    def __init__(
        self,
        url_base: str,
        leer_clave: Callable[[], str | None],
        *,
        dormir: Callable[[float], None] = time.sleep,
        tiempo_generar: float = 180.0,
        tiempo_probar: float = 20.0,
    ) -> None:
        self.url_base = url_base.rstrip("/")
        self._leer_clave = leer_clave
        self._dormir = dormir
        self._tiempo_generar = tiempo_generar
        self._tiempo_probar = tiempo_probar
        # Con el simulador local no se usa ningún proxy del sistema.
        self._local = urlparse(self.url_base).hostname in ("127.0.0.1", "localhost")

    # --- Las dos llamadas ----------------------------------------------------------------------------------------

    def probar(self) -> EstadoClave:
        """Consulta `GET /key`: el límite de la clave, lo que queda y lo usado. No gasta."""
        cuerpo = self._pedir("GET", "/key", None, self._tiempo_probar, None)
        datos = cuerpo.get("data") if isinstance(cuerpo, dict) and isinstance(cuerpo.get("data"), dict) else cuerpo
        datos = datos if isinstance(datos, dict) else {}
        return EstadoClave(
            limite=_importe(datos.get("limit")),
            restante=_importe(datos.get("limit_remaining")),
            usado=_importe(datos.get("usage")),
        )

    def generar(
        self,
        modelo: str,
        texto: str,
        formato: str,
        referencia_jpeg: bytes,
        al_esperar: Callable[[str], None] | None = None,
    ) -> Imagen:
        """Pide una escena: `POST /images` con el producto sobre blanco como referencia. Esto sí gasta."""
        peticion = {
            "model": modelo,
            "prompt": texto,
            "aspect_ratio": formato,
            "resolution": "1K",
            "input_references": [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(referencia_jpeg).decode("ascii")},
                }
            ],
        }
        cuerpo = self._pedir("POST", "/images", peticion, self._tiempo_generar, al_esperar)

        datos = None
        try:
            datos = base64.b64decode(cuerpo["data"][0]["b64_json"], validate=True)
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
            pass
        if not datos or detectar_tipo(datos[:32]) not in ("jpeg", "png", "webp"):
            # Respondió bien pero sin imagen: el modelo no quiso (o no pudo) generar la escena.
            codigo_interno = cuerpo.get("error", {}).get("code") if isinstance(cuerpo, dict) and isinstance(cuerpo.get("error"), dict) else None
            if isinstance(codigo_interno, int) and codigo_interno >= 400:
                raise self._error(clasificar(codigo_interno, cuerpo), codigo_interno)
            raise ErrorOpenRouter("filtro")
        uso = cuerpo.get("usage") if isinstance(cuerpo.get("usage"), dict) else {}
        return Imagen(datos=datos, costo=_importe(uso.get("cost")))

    # --- Por dentro ----------------------------------------------------------------------------------------------

    def _pedir(self, metodo: str, ruta: str, json: dict | None, tiempo: float, al_esperar) -> dict:
        clave = self._leer_clave()
        if not clave:
            raise ErrorOpenRouter("sin_clave")
        cabeceras = {"Authorization": f"Bearer {clave}", "Accept": "application/json"}
        limites = httpx.Timeout(tiempo, connect=10.0)

        for intento in range(REINTENTOS + 1):
            try:
                with httpx.Client(timeout=limites, trust_env=not self._local, follow_redirects=False) as cliente:
                    respuesta = cliente.request(metodo, self.url_base + ruta, headers=cabeceras, json=json)
            except httpx.ConnectTimeout:
                raise ErrorOpenRouter("conexion") from None
            except httpx.TimeoutException:
                raise ErrorOpenRouter("tiempo", posible_cobro=metodo == "POST") from None
            except httpx.HTTPError:
                raise ErrorOpenRouter("conexion") from None

            try:
                cuerpo = respuesta.json()
            except ValueError:
                cuerpo = {}
            if respuesta.status_code == 200:
                return cuerpo if isinstance(cuerpo, dict) else {}

            tipo = clasificar(respuesta.status_code, cuerpo)
            if tipo != "reintentar":
                raise self._error(tipo, respuesta.status_code)
            if intento == REINTENTOS:
                break
            segundos = _espera(respuesta.headers)
            if al_esperar:
                al_esperar(mensaje_espera(segundos))
            self._dormir(segundos)
        raise ErrorOpenRouter("espera", MENSAJES["espera_agotada"])

    @staticmethod
    def _error(tipo: str, codigo: int) -> ErrorOpenRouter:
        if tipo == "otro":
            return ErrorOpenRouter("otro", mensaje_otro(codigo))
        if tipo == "reintentar":
            return ErrorOpenRouter("espera", MENSAJES["espera_agotada"])
        return ErrorOpenRouter(tipo)


def _importe(valor: object) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)
