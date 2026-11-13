"""El servidor: la página y su API, solo para este computador.

- Atiende únicamente peticiones dirigidas a `127.0.0.1` o `localhost`, y solo desde su propia página (`Host`,
  `Origin`): otra web abierta en el navegador no puede usar la herramienta ni gastar.
- La página no carga nada de internet (política CSP: solo archivos propios).
- Los errores salen en español, con la forma `{"error": "…"}`, y nunca repiten lo que se envió.
- La clave no aparece en ninguna respuesta: solo «••••» y sus 4 últimos caracteres.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders, UploadFile
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import HERRAMIENTA, VERSION
from .ajustes import LOGO_MAX_MB
from .config import Config
from .estudio import ErrorEstudio, Estudio
from .registro import registro
from .subidas import MAX_BYTES, MAX_FOTOS, MENSAJE_DEMASIADAS

MAX_JSON = 64 * 1024  # ninguna petición JSON de la página pasa de unos pocos KB
MAX_SUBIDA = MAX_FOTOS * MAX_BYTES + 2 * 1024 * 1024  # 20 fotos de 25 MB y los separadores del formulario
MAX_SUBIDA_LOGO = (LOGO_MAX_MB + 1) * 1024 * 1024
MAX_ARCHIVOS_FORMULARIO = 100  # se leen más de 20 para poder decir «hasta 20 fotos a la vez» en vez de un error raro

_HOST = re.compile(r"^(127\.0\.0\.1|localhost)(:\d{1,5})?$")

MENSAJES = {
    400: "La petición no se entiende.",
    403: "Esta herramienta solo se puede usar desde su propia página, en este computador.",
    404: "Esa dirección no existe.",
    405: "Esa acción no está permitida aquí.",
    411: "La subida no dice cuánto pesa. Vuelve a intentarlo desde la página.",
    413: "La subida pesa demasiado: sube menos fotos a la vez (hasta 20, de 25 MB cada una).",
    415: "Los datos deben enviarse como JSON.",
    422: "Los datos enviados no tienen la forma esperada.",
    500: "Algo falló dentro de la herramienta. Inténtalo otra vez.",
}

# Política de la página: solo archivos propios. Nada de internet: ni fuentes, ni librerías, ni iconos.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
CABECERAS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}


# FastAPI puede enviar trazas y métricas (OpenTelemetry) a un servidor si se le configura por variables de entorno.
# Aquí queda apagado del todo: la herramienta no envía nada a ningún sitio, diga lo que diga el entorno.
SIN_TELEMETRIA = {"tracing": False, "metrics": False, "logs": False, "operation_spans": False, "auto_configure": False}


class ErrorPeticion(Exception):
    """La petición no vale; se responde con el código y su mensaje fijo."""

    def __init__(self, codigo: int, mensaje: str | None = None) -> None:
        super().__init__(mensaje or MENSAJES[codigo])
        self.codigo = codigo


def _error(codigo: int, mensaje: str | None = None) -> JSONResponse:
    return JSONResponse({"error": mensaje or MENSAJES.get(codigo, MENSAJES[500])}, status_code=codigo)


class Guardia:
    """Deja pasar solo lo que viene de la propia página, y pone las cabeceras de seguridad en cada respuesta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            if scope["type"] == "lifespan":
                await self.app(scope, receive, send)
            return  # no hay websockets ni nada más

        cabeceras = Headers(scope=scope)
        host = cabeceras.get("host", "")
        ruta = scope.get("path", "")

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                salida = MutableHeaders(scope=mensaje)
                for nombre, valor in CABECERAS.items():
                    salida[nombre] = valor
                if ruta.startswith("/api/") or ruta == "/":
                    salida["Cache-Control"] = "no-store"
            await send(mensaje)

        rechazo = None
        if not _HOST.fullmatch(host):
            rechazo = _error(400, MENSAJES[403])
        else:
            origen = cabeceras.get("origin")
            if origen is not None and origen != f"http://{host}":
                rechazo = _error(403)
            elif ruta.startswith("/api/") and cabeceras.get("sec-fetch-site") in ("cross-site", "same-site"):
                rechazo = _error(403)
        if rechazo is not None:
            await rechazo(scope, receive, enviar)
            return

        empezada = False

        async def enviar_y_anotar(mensaje: Message) -> None:
            nonlocal empezada
            empezada = empezada or mensaje["type"] == "http.response.start"
            await enviar(mensaje)

        try:
            await self.app(scope, receive, enviar_y_anotar)
        except Exception as error:
            # Un fallo interno se anota solo con su tipo (las trazas llevan rutas del computador) y se responde
            # con un mensaje fijo: nunca sale el detalle.
            registro.error("Error interno en %s %s (%s)", scope.get("method", ""), ruta, type(error).__name__)
            if not empezada:
                await _error(500)(scope, receive, enviar)


async def _leer_json(peticion: Request) -> dict:
    """El cuerpo JSON de una petición de la página: un objeto, de tamaño razonable."""
    tipo = peticion.headers.get("content-type", "").split(";")[0].strip().lower()
    if tipo != "application/json":
        raise ErrorPeticion(415)
    datos = b""
    async for trozo in peticion.stream():
        datos += trozo
        if len(datos) > MAX_JSON:
            raise ErrorPeticion(413, "Los datos enviados son demasiado grandes.")
    try:
        cuerpo = json.loads(datos)
    except (ValueError, UnicodeDecodeError):
        raise ErrorPeticion(422) from None
    if not isinstance(cuerpo, dict):
        raise ErrorPeticion(422)
    return cuerpo


def _lista(valor: object) -> list[str]:
    """Una lista de identificadores (textos cortos). Cualquier otra cosa no vale."""
    if not isinstance(valor, list) or len(valor) > 200 or not all(isinstance(v, str) and len(v) <= 100 for v in valor):
        raise ErrorPeticion(422)
    return valor


def _comprobar_peso(peticion: Request, maximo: int) -> None:
    """El tamaño de una subida se mira antes de recibirla."""
    declarado = peticion.headers.get("content-length", "")
    if not declarado.isdigit():
        raise ErrorPeticion(411)
    if int(declarado) > maximo:
        raise ErrorPeticion(413)


async def _archivos_subidos(peticion: Request, campo: str, maximo: int) -> list[UploadFile]:
    if peticion.headers.get("content-type", "").split(";")[0].strip().lower() != "multipart/form-data":
        raise ErrorPeticion(415, "Las fotos deben enviarse desde la página.")
    _comprobar_peso(peticion, maximo)
    try:
        formulario = await peticion.form(max_files=MAX_ARCHIVOS_FORMULARIO, max_fields=20)
    except HTTPException:
        # O el formulario está mal formado, o trae muchísimos archivos: en los dos casos no se guarda nada.
        raise ErrorPeticion(400, MENSAJE_DEMASIADAS if campo == "fotos" else None) from None
    return [valor for valor in formulario.getlist(campo) if isinstance(valor, UploadFile)]


def _a_disco(subida: UploadFile, carpeta: Path) -> Path:
    """Copia una subida a un archivo de `trabajo/` (con un nombre nuestro, nunca el que llegó)."""
    destino = carpeta / uuid.uuid4().hex
    subida.file.seek(0)
    with open(destino, "wb") as salida:
        shutil.copyfileobj(subida.file, salida, 1024 * 1024)
    return destino


def crear_aplicacion(config: Config, estudio: Estudio | None = None) -> FastAPI:
    """La aplicación web. Sin documentación automática: carga librerías de internet y está en inglés."""
    propio = estudio is None
    if estudio is None:
        estudio = Estudio(config)
        estudio.limpiar_trabajo()  # los temporales de la vez anterior
    subidas = config.trabajo / "subidas"
    subidas.mkdir(parents=True, exist_ok=True)
    # Los temporales de las subidas también quedan dentro de la carpeta de la herramienta.
    tempfile.tempdir = str(subidas)

    @asynccontextmanager
    async def vida(_: FastAPI):
        yield
        if propio:
            estudio.cerrar()

    app = FastAPI(
        title=HERRAMIENTA, version=VERSION, docs_url=None, redoc_url=None, openapi_url=None, lifespan=vida,
        telemetry=SIN_TELEMETRIA,
    )
    app.state.estudio = estudio
    app.add_middleware(Guardia)

    # --- Errores: en español y sin repetir lo que se envió ---------------------------------------------------------

    @app.exception_handler(ErrorEstudio)
    async def _(peticion: Request, error: ErrorEstudio) -> JSONResponse:
        return _error(error.codigo, str(error))

    @app.exception_handler(ErrorPeticion)
    async def _(peticion: Request, error: ErrorPeticion) -> JSONResponse:
        return _error(error.codigo, str(error))

    @app.exception_handler(HTTPException)
    async def _(peticion: Request, error: HTTPException) -> JSONResponse:
        return _error(error.status_code if error.status_code in MENSAJES else 400)

    @app.exception_handler(RequestValidationError)
    async def _(peticion: Request, error: RequestValidationError) -> JSONResponse:
        return _error(422)

    # --- La página y sus archivos, todos locales -------------------------------------------------------------------

    @app.get("/")
    def pagina() -> FileResponse:
        indice = config.web / "index.html"
        if not indice.is_file():
            raise ErrorPeticion(404)
        return FileResponse(indice, media_type="text/html; charset=utf-8")

    for ruta, carpeta in (("/web", config.web), ("/estilo", config.estilo), ("/marca", config.marca)):
        if carpeta.is_dir():
            app.mount(ruta, StaticFiles(directory=carpeta), name=ruta.strip("/"))

    # --- Estado ----------------------------------------------------------------------------------------------------

    @app.get("/api/estado")
    def estado() -> dict:
        return estudio.publico()

    @app.get("/api/opciones")
    def opciones() -> dict:
        return estudio.opciones()

    # --- Fotos -----------------------------------------------------------------------------------------------------

    @app.post("/api/fotos")
    async def subir_fotos(peticion: Request) -> dict:
        try:
            archivos = await _archivos_subidos(peticion, "fotos", MAX_SUBIDA)
            if not archivos:
                raise ErrorPeticion(400, "No llegó ninguna foto.")
            if len(archivos) > MAX_FOTOS:
                raise ErrorPeticion(400, MENSAJE_DEMASIADAS)

            def guardar() -> list[dict]:
                return [
                    estudio.agregar_foto(_a_disco(archivo, subidas), archivo.filename or "foto") for archivo in archivos
                ]

            return {"fotos": await run_in_threadpool(guardar)}
        finally:
            await peticion.close()  # borra los temporales de la subida

    @app.delete("/api/fotos/{foto_id}")
    def quitar_foto(foto_id: str) -> dict:
        estudio.quitar_foto(foto_id)
        return {"ok": True}

    @app.delete("/api/fotos")
    def empezar_de_nuevo() -> dict:
        estudio.empezar_de_nuevo()
        return {"ok": True}

    @app.post("/api/modelo/reintentar")
    def reintentar_modelo() -> dict:
        estudio.reintentar_modelo()
        return {"ok": True}

    @app.get("/api/fotos/{foto_id}/vista")
    def vista(foto_id: str) -> FileResponse:
        return _imagen(estudio.foto(foto_id).vista, "image/jpeg")

    @app.get("/api/fotos/{foto_id}/recorte")
    def vista_recorte(foto_id: str) -> FileResponse:
        return _imagen(estudio.foto(foto_id).vista_recorte, "image/webp")

    # --- Medidas, archivos y descarga --------------------------------------------------------------------------------

    @app.post("/api/medidas")
    async def medidas(peticion: Request) -> dict:
        cuerpo = await _leer_json(peticion)
        fotos, plataformas = _lista(cuerpo.get("fotos")), _lista(cuerpo.get("plataformas"))
        return {"archivos": await run_in_threadpool(estudio.generar_medidas, fotos, plataformas)}

    @app.get("/api/archivos/{foto_id}/{nombre}")
    def archivo(foto_id: str, nombre: str) -> FileResponse:
        ruta = estudio.archivo(foto_id, nombre)  # solo archivos que el estudio creó y tiene anotados
        return FileResponse(ruta, filename=ruta.name, content_disposition_type="inline")

    @app.get("/api/descargar")
    def descargar(plataforma: str | None = None) -> FileResponse:
        ruta = estudio.descargar(plataforma)
        return FileResponse(ruta, filename=ruta.name, media_type="application/zip")

    # --- Ajustes -------------------------------------------------------------------------------------------------------

    @app.put("/api/ajustes")
    async def cambiar_ajustes(peticion: Request) -> dict:
        cuerpo = await _leer_json(peticion)
        await run_in_threadpool(estudio.cambiar_ajustes, cuerpo)
        return {"ok": True}

    @app.post("/api/ajustes/logo")
    async def poner_logo(peticion: Request) -> dict:
        try:
            archivos = await _archivos_subidos(peticion, "logo", MAX_SUBIDA_LOGO)
            if len(archivos) != 1:
                raise ErrorPeticion(400, "Elige un solo archivo para el logo.")

            def guardar() -> None:
                temporal = _a_disco(archivos[0], subidas)
                try:
                    estudio.guardar_logo(temporal)
                finally:
                    temporal.unlink(missing_ok=True)

            await run_in_threadpool(guardar)
            return {"ok": True}
        finally:
            await peticion.close()

    @app.delete("/api/ajustes/logo")
    def quitar_logo() -> dict:
        estudio.quitar_logo()
        return {"ok": True}

    @app.get("/api/logo")
    def logo() -> FileResponse:
        return _imagen(config.logo, "image/png")

    @app.put("/api/ajustes/clave")
    async def guardar_clave(peticion: Request) -> dict:
        cuerpo = await _leer_json(peticion)
        await run_in_threadpool(estudio.guardar_clave, cuerpo.get("clave"))
        return {"clave": estudio.publico()["clave"]}  # solo «••••» y los 4 últimos caracteres

    @app.delete("/api/ajustes/clave")
    def borrar_clave() -> dict:
        estudio.borrar_clave()
        return {"clave": estudio.publico()["clave"]}

    @app.post("/api/ajustes/clave/probar")
    def probar_clave() -> dict:
        return {"mensaje": estudio.probar_clave()}

    # --- Escenas con IA --------------------------------------------------------------------------------------------

    @app.post("/api/escenas/estimar")
    async def estimar_escenas(peticion: Request) -> dict:
        cuerpo = await _leer_json(peticion)
        return await run_in_threadpool(
            estudio.estimar_escenas, _lista(cuerpo.get("fotos")), cuerpo.get("escena"), cuerpo.get("formato"),
            cuerpo.get("propia"),
        )

    @app.post("/api/escenas")
    async def generar_escenas(peticion: Request) -> dict:
        cuerpo = await _leer_json(peticion)
        fotos = _lista(cuerpo.get("fotos"))

        def generar() -> dict:
            return estudio.generar_escenas(
                fotos, cuerpo.get("escena"), cuerpo.get("formato"), cuerpo.get("propia"),
                confirmado=cuerpo.get("confirmado"), costo_visto=cuerpo.get("costo_estimado_usd"),
            )

        return await run_in_threadpool(generar)

    return app


def _imagen(ruta: Path, tipo: str) -> FileResponse:
    if not ruta.is_file():
        raise ErrorPeticion(404)
    return FileResponse(ruta, media_type=tipo)
