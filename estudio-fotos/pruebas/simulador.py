"""Un OpenRouter de mentira, en este mismo computador, para que las pruebas nunca llamen al de verdad.

Atiende las dos rutas que usa la herramienta (`GET /api/v1/key` y `POST /api/v1/images`) y rechaza cualquier
petición que no tenga exactamente la forma que da la ficha (punto 4.4): así el contrato queda probado aunque no
se gaste ni un centavo.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import threading
import time

import uvicorn
from PIL import Image, ImageDraw
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

MODELOS = {
    "google/gemini-nano-banana-2.1",
    "google/gemini-3.1-flash-lite-image",
    "google/gemini-3.1-flash-image",
    "google/gemini-3-pro-image",
}
# Lo que «devuelve el modelo» para cada formato. El 4:5 no es exacto a propósito: los modelos de verdad tampoco.
MEDIDAS = {"1:1": (1024, 1024), "4:5": (928, 1152), "16:9": (1344, 768)}


def error(codigo: int, mensaje: str = "error", **metadatos) -> dict:
    """Una respuesta de error con la forma de las de OpenRouter, para poner en el guion."""
    cuerpo = {"error": {"code": codigo, "message": mensaje}}
    if metadatos:
        cuerpo["error"]["metadata"] = metadatos
    return {"codigo": codigo, "cuerpo": cuerpo}


class Simulador:
    def __init__(self) -> None:
        self._servidor: uvicorn.Server | None = None
        self._hilo: threading.Thread | None = None
        self.puerto = 0
        self.reiniciar()

    def reiniciar(self) -> None:
        self.clave: str | None = None  # la clave que se acepta
        self.costo = 0.038  # `usage.cost` de cada imagen
        self.llave = {"label": "pruebas", "limit": 2.0, "limit_remaining": 1.88, "usage": 0.12}
        self.llave_suelta = False  # True: /key responde sin envolver en «data»
        self.guion: list[dict] = []  # respuestas preparadas para /images; cuando se acaba, éxito
        self.demora = 0.0  # segundos que tarda /images
        self.peticiones: list[dict] = []
        self.violaciones: list[str] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}/api/v1"

    def imagenes_pedidas(self) -> list[dict]:
        return [p for p in self.peticiones if p["ruta"] == "/api/v1/images"]

    # --- Rutas ---------------------------------------------------------------------------------------------------

    def _autorizada(self, peticion: Request) -> bool:
        return self.clave is not None and peticion.headers.get("authorization") == f"Bearer {self.clave}"

    async def _key(self, peticion: Request) -> JSONResponse:
        autorizada = self._autorizada(peticion)
        self.peticiones.append({"metodo": "GET", "ruta": peticion.url.path, "autorizada": autorizada})
        if not autorizada:
            return JSONResponse({"error": {"code": 401, "message": "No auth credentials found"}}, status_code=401)
        return JSONResponse(self.llave if self.llave_suelta else {"data": self.llave})

    async def _images(self, peticion: Request) -> JSONResponse:
        autorizada = self._autorizada(peticion)
        try:
            cuerpo = json.loads(await peticion.body())
        except ValueError:
            cuerpo = None
        self.peticiones.append({"metodo": "POST", "ruta": peticion.url.path, "autorizada": autorizada, "cuerpo": cuerpo})
        if not autorizada:
            return JSONResponse({"error": {"code": 401, "message": "Invalid credentials"}}, status_code=401)

        fallo = self._contrato(cuerpo)
        if fallo:
            self.violaciones.append(fallo)
            return JSONResponse({"error": {"code": 400, "message": f"contrato: {fallo}"}}, status_code=400)

        # La respuesta se decide antes de la demora: una petición lenta de una prueba no puede quedarse con el guion
        # de la siguiente.
        respuesta = self.guion.pop(0) if self.guion else None
        if self.demora:
            await asyncio.sleep(self.demora)
        if respuesta:
            return JSONResponse(respuesta["cuerpo"], status_code=respuesta["codigo"], headers=respuesta.get("cabeceras"))
        return JSONResponse({
            "data": [{"b64_json": base64.b64encode(_escena(cuerpo["aspect_ratio"])).decode("ascii")}],
            "usage": {"cost": self.costo},
        })

    @staticmethod
    def _contrato(cuerpo: object) -> str | None:
        """Comprueba la forma exacta de la petición de la ficha. Devuelve qué falla, o None."""
        if not isinstance(cuerpo, dict):
            return "el cuerpo no es un objeto JSON"
        if set(cuerpo) != {"model", "prompt", "aspect_ratio", "resolution", "input_references"}:
            return f"campos inesperados: {sorted(cuerpo)}"
        if cuerpo["model"] not in MODELOS:
            return "model no es uno de los cuatro de la ficha"
        if not isinstance(cuerpo["prompt"], str) or len(cuerpo["prompt"]) < 40:
            return "falta el prompt"
        if cuerpo["aspect_ratio"] not in MEDIDAS:
            return "aspect_ratio no es 1:1, 4:5 ni 16:9"
        if cuerpo["resolution"] != "1K":
            return "resolution no es «1K»"
        referencias = cuerpo["input_references"]
        if not isinstance(referencias, list) or len(referencias) != 1:
            return "input_references no es una lista de un elemento"
        referencia = referencias[0]
        if not isinstance(referencia, dict) or set(referencia) != {"type", "image_url"} or referencia["type"] != "image_url":
            return "la referencia no es {type: image_url, image_url: {url}}"
        url = referencia["image_url"].get("url") if isinstance(referencia["image_url"], dict) else None
        if set(referencia["image_url"]) != {"url"} or not isinstance(url, str) or not url.startswith("data:image/jpeg;base64,"):
            return "la referencia no es una data URL image/jpeg en base64"
        try:
            datos = base64.b64decode(url.split(",", 1)[1], validate=True)
            with Image.open(io.BytesIO(datos)) as imagen:
                if imagen.format != "JPEG":
                    return "la referencia no es un JPEG"
                if imagen.convert("RGB").getpixel((0, 0)) != (255, 255, 255):
                    return "la referencia no es el producto sobre fondo blanco"
        except Exception:
            return "la referencia no se puede abrir"
        return None

    # --- Arranque ------------------------------------------------------------------------------------------------

    def arrancar(self) -> "Simulador":
        aplicacion = Starlette(routes=[
            Route("/api/v1/key", self._key, methods=["GET"]),
            Route("/api/v1/images", self._images, methods=["POST"]),
        ])
        self._servidor = uvicorn.Server(uvicorn.Config(aplicacion, host="127.0.0.1", port=0, log_level="critical"))
        self._hilo = threading.Thread(target=self._servidor.run, name="simulador-openrouter", daemon=True)
        self._hilo.start()
        limite = time.monotonic() + 10
        while not self._servidor.started:
            assert time.monotonic() < limite, "el simulador de OpenRouter no arrancó"
            time.sleep(0.01)
        self.puerto = self._servidor.servers[0].sockets[0].getsockname()[1]
        return self

    def parar(self) -> None:
        if self._servidor:
            self._servidor.should_exit = True
        if self._hilo:
            self._hilo.join(timeout=5)


def _escena(formato: str) -> bytes:
    """Una «escena» inventada: un degradado con un rectángulo, en PNG, con la medida del formato."""
    ancho, alto = MEDIDAS[formato]
    imagen = Image.linear_gradient("L").resize((ancho, alto)).convert("RGB")
    ImageDraw.Draw(imagen).rectangle((ancho // 3, alto // 4, ancho * 2 // 3, alto * 3 // 4), fill=(150, 70, 40))
    memoria = io.BytesIO()
    imagen.save(memoria, "PNG")
    return memoria.getvalue()
