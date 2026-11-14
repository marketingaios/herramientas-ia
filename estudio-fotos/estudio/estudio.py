"""El estudio: las fotos de la sesión, la cola de recorte y los trabajos en lote.

Todo el estado vive en memoria, protegido con un candado. Una «sesión» va desde que arranca el servidor hasta que se
cierra; sus resultados quedan en `salidas/<fecha_hora>/`.
"""

from __future__ import annotations

import shutil
import statistics
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from . import HERRAMIENTA, VERSION, costos, descargas, equipo
from . import ajustes as los_ajustes
from . import clave as la_clave
from . import escenas as las_escenas
from .config import Config
from .encuadre import Salida, exportar
from .openrouter import MENSAJES as MENSAJES_OPENROUTER
from .openrouter import Cliente, ErrorOpenRouter
from .plataformas import ErrorPlataformas, Plataforma
from .plataformas import cargar as cargar_plataformas
from .recorte import (
    MENSAJE_DESCARGANDO,
    MODELOS,
    ErrorRecorte,
    Recortador,
    RecortadorRembg,
    RecortadorSimulado,
    mensaje_descarga,
    recortar,
)
from .registro import registro
from .subidas import MAX_FOTOS, MAX_MB, ErrorFoto, abrir_normalizada, limpiar_nombre, numero, validar

LADO_VISTA = 1400  # lado mayor de las vistas previas de la página
EXTENSIONES = {"jpeg": "jpg", "png": "png", "webp": "webp"}

MENSAJE_RECORTE_FALLIDO = "No se pudo recortar esta foto. Quítala y vuelve a subirla."
MENSAJE_MODELO_NO_CARGA = (
    "No se pudo preparar el modelo de recorte. Cierra otros programas para liberar memoria y vuelve a intentarlo."
)
MENSAJE_SIN_CONFIRMAR = "Antes de gastar hay que ver el costo estimado y confirmarlo."
MENSAJE_ESCENA_DANADA = "OpenRouter devolvió una imagen que no se pudo guardar. Esa escena sí se cobró."
MENSAJE_ESCENA_FALLIDA = "No se pudo preparar esta escena. Inténtalo otra vez."


class ErrorEstudio(Exception):
    """Algo que el usuario pidió no se puede hacer; el mensaje dice qué pasó y qué hacer."""

    def __init__(self, mensaje: str, codigo: int = 400) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass
class Foto:
    id: str
    nombre: str  # limpio y único en la sesión: con él se nombran los archivos de resultados
    archivo: str  # nombre con extensión, como se muestra
    ancho: int
    alto: int
    carpeta: Path  # trabajo/<id>/
    original: Path
    aviso: str | None = None
    estado: str = "en_cola"  # en_cola · recortando · lista · error
    error: str | None = None
    segundos: float | None = None
    cobertura: float | None = None
    porcentaje: float | None = None  # cuánto ocupa el producto en la foto original (lado que más llena)
    recorte: Path | None = None  # el PNG con transparencia, en salidas/
    peso_recorte: int = 0
    salidas: dict = field(default_factory=dict)  # id de plataforma → Salida
    escenas: list = field(default_factory=list)

    @property
    def vista(self) -> Path:
        return self.carpeta / "vista.jpg"

    @property
    def vista_recorte(self) -> Path:
        return self.carpeta / "recorte.webp"


@dataclass
class Trabajo:
    """Un trabajo en lote con su avance: «3 de 5 · foto_3.jpg · 4,2 s»."""

    tipo: str
    estado: str = "inactivo"  # inactivo · trabajando · terminado
    total: int = 0
    hechos: int = 0
    actual: str | None = None
    mensaje: str | None = None
    errores: list = field(default_factory=list)
    inicio: float = 0.0
    inicio_actual: float = 0.0
    segundos_total: float = 0.0
    extra: dict = field(default_factory=dict)

    def empezar(self, total: int = 0) -> None:
        self.estado, self.total, self.hechos = "trabajando", total, 0
        self.actual, self.mensaje, self.errores, self.extra = None, None, [], {}
        self.inicio = time.monotonic()
        self.segundos_total = 0.0

    def empezar_archivo(self, nombre: str) -> None:
        self.actual, self.mensaje = nombre, None
        self.inicio_actual = time.monotonic()

    def terminar_archivo(self, error: str | None = None) -> None:
        if error:
            self.errores.append({"archivo": self.actual, "mensaje": error})
        self.hechos += 1
        self.actual = None

    def terminar(self) -> None:
        self.estado, self.actual = "terminado", None
        self.segundos_total = time.monotonic() - self.inicio

    def texto(self) -> str:
        if self.estado == "inactivo":
            return ""
        if self.estado == "trabajando":
            if self.actual:
                segundos = time.monotonic() - self.inicio_actual
                return f"{min(self.hechos + 1, self.total)} de {self.total} · {self.actual} · {numero(segundos)} s"
            espera = f" · {self.mensaje}" if self.mensaje else ""
            return f"{self.hechos} de {self.total}{espera}"
        fallos = len(self.errores)
        final = "listo" if not fallos else (f"{fallos} con error" if fallos > 1 else "1 con error")
        return f"{self.hechos} de {self.total} · {final} · {numero(self.segundos_total)} s en total"

    def publico(self) -> dict:
        return {
            "estado": self.estado,
            "total": self.total,
            "hechos": self.hechos,
            "actual": self.actual,
            "mensaje": self.mensaje,
            "texto": self.texto(),
            "errores": list(self.errores),
            **self.extra,
        }


@dataclass
class EstadoModelo:
    nombre: str = ""
    etiqueta: str = ""
    nota: str | None = None
    estado: str = "sin_cargar"  # sin_cargar · descargando · preparando · listo · error
    mensaje: str | None = None
    descargado_mb: int = 0
    total_mb: int = 0

    def publico(self) -> dict:
        return {
            "nombre": self.nombre,
            "etiqueta": self.etiqueta,
            "nota": self.nota,
            "estado": self.estado,
            "mensaje": self.mensaje,
            "descargado_mb": self.descargado_mb,
            "total_mb": self.total_mb,
        }


class Estudio:
    def __init__(
        self,
        config: Config,
        fabrica_recortador: Callable[[str], Recortador] | None = None,
        dormir: Callable[[float], None] = time.sleep,
        aceleracion: equipo.Aceleracion | None = None,
    ) -> None:
        self.config = config
        self._dormir = dormir  # cómo se espera cuando OpenRouter pide esperar (las pruebas no esperan de verdad)
        self.config.preparar_carpetas()
        self._candado = threading.RLock()
        self._hay_trabajo = threading.Condition(self._candado)
        self._fabrica = fabrica_recortador or self._fabrica_por_defecto
        self._recortador: Recortador | None = None
        self._modelo_recortador: str | None = None
        self._modelo_bloqueado = False
        # La aceleración se mide con el modelo de verdad, nunca con el recortador simulado de las pruebas.
        if aceleracion is None and config.medir and config.recortador == "rembg" and fabrica_recortador is None:
            aceleracion = equipo.Aceleracion(config.medicion, config.modelos, config.trabajo)
        self._aceleracion = aceleracion
        self._midiendo = False
        self._por_medir = False  # un lote acaba de terminar y falta decidir si toca medir
        self._renovar_recortador = False  # la medición eligió el acelerador: el próximo lote prepara el modelo con él
        self._tiempos_modelo: dict[str, list[float]] = {}  # lo que tarda el modelo por foto, con el procesador
        self._pendientes: deque[str] = deque()
        self._hilo_recorte: threading.Thread | None = None
        self._cerrado = False

        self.fotos: dict[str, Foto] = {}
        self.trabajos = {tipo: Trabajo(tipo) for tipo in ("recorte", "medidas", "escenas")}
        self.modelo = EstadoModelo()
        self.ajustes = los_ajustes.cargar(config.ajustes)
        self.calidad_recorte = self.ajustes["calidad_recorte"]
        self.aviso_puerto: str | None = None
        # Lo gastado en escenas desde que arrancó la herramienta: contra esto se compara el tope de la sesión.
        self.gasto_sesion = 0.0
        self.sesion = ""
        self._nueva_sesion()
        self._anunciar_modelo()

    # --- Sesión y carpetas ---------------------------------------------------------------------------------------

    def _nueva_sesion(self) -> None:
        base = time.strftime("%Y-%m-%d_%H%M%S")
        nombre, n = base, 2
        while (self.config.salidas / nombre).exists():
            nombre, n = f"{base}-{n}", n + 1
        self.sesion = nombre

    @property
    def carpeta_salidas(self) -> Path:
        return self.config.salidas / self.sesion

    def limpiar_trabajo(self) -> None:
        """Vacía los archivos temporales (las fotos subidas, entre otros). Se llama al arrancar y al cerrar."""
        try:
            elementos = list(self.config.trabajo.iterdir())
        except OSError:
            return  # no hay carpeta: nada que vaciar
        for elemento in elementos:
            try:
                if elemento.is_dir() and not elemento.is_symlink():
                    shutil.rmtree(elemento, ignore_errors=True)
                else:
                    elemento.unlink(missing_ok=True)
            except OSError:
                pass  # un archivo en uso (Windows): se borrará en el siguiente arranque

    def cerrar(self) -> None:
        with self._hay_trabajo:
            self._cerrado = True
            self._hay_trabajo.notify_all()
        if self._aceleracion is not None:
            self._aceleracion.cancelar()  # si la prueba del acelerador está en marcha, se corta
        if self._hilo_recorte:
            self._hilo_recorte.join(timeout=10)

    # --- El modelo de recorte ------------------------------------------------------------------------------------

    def _fabrica_por_defecto(self, modelo: str) -> Recortador:
        if self.config.recortador == "simulado":
            return RecortadorSimulado()
        proveedores = self._aceleracion.proveedores_para(modelo) if self._aceleracion else equipo.proveedores_para()
        return RecortadorRembg(modelo, self.config.modelos, proveedores)

    def _eleccion(self) -> equipo.Eleccion:
        return equipo.elegir_modelo(self.calidad_recorte)

    def _anunciar_modelo(self) -> None:
        """Deja dicho en el estado qué modelo toca, aunque todavía no se haya cargado."""
        eleccion = self._eleccion()
        with self._candado:
            cambia = eleccion.modelo != self.modelo.nombre
            self.modelo.nombre = eleccion.modelo
            self.modelo.etiqueta = eleccion.etiqueta
            self.modelo.nota = eleccion.nota
            self.modelo.total_mb = MODELOS[eleccion.modelo]["mb"]
            if cambia:
                listo = self._recortador is not None and self._modelo_recortador == eleccion.modelo
                self.modelo.estado = "listo" if listo else "sin_cargar"
                self.modelo.mensaje = None
                self.modelo.descargado_mb = 0

    def cambiar_calidad(self, calidad: str) -> None:
        if calidad not in equipo.CALIDADES:
            raise ErrorEstudio("La calidad del recorte debe ser Automática, Máxima o Rápida.")
        with self._hay_trabajo:
            self.calidad_recorte = calidad
            self._anunciar_modelo()
            self._modelo_bloqueado = False
            self._hay_trabajo.notify_all()

    def reintentar_modelo(self) -> None:
        """Vuelve a intentar la descarga del modelo después de un fallo."""
        with self._hay_trabajo:
            if self.modelo.estado == "error":
                self.modelo.estado, self.modelo.mensaje = "sin_cargar", None
            self._modelo_bloqueado = False
            self._hay_trabajo.notify_all()

    def _asegurar_recortador(self) -> Recortador | None:
        """El recortador del modelo que toca, listo para usar. Se crea una sola vez y se reutiliza en todo el lote."""
        eleccion = self._eleccion()
        with self._candado:
            # Si la medición eligió el acelerador, el modelo se vuelve a preparar al empezar un lote, nunca a mitad.
            renovar = self._renovar_recortador and self.trabajos["recorte"].hechos == 0
            if renovar:
                self._renovar_recortador = False
                self._recortador = self._modelo_recortador = None  # suelta la memoria del anterior antes de preparar
        if self._recortador is not None and self._modelo_recortador == eleccion.modelo:
            return self._recortador

        self._anunciar_modelo()
        try:
            recortador = self._fabrica(eleccion.modelo)
            if not recortador.descargado():
                with self._candado:
                    self.modelo.estado = "descargando"
                    self.modelo.mensaje = mensaje_descarga(eleccion.modelo)
                    self.modelo.descargado_mb = 0
                    self.trabajos["recorte"].mensaje = MENSAJE_DESCARGANDO
                registro.info("Descargando el modelo de recorte %s (solo la primera vez)", eleccion.modelo)
                recortador.descargar(self._avance_descarga)
            with self._candado:
                self.modelo.estado, self.modelo.mensaje = "preparando", "Preparando el modelo de recorte…"
                self.trabajos["recorte"].mensaje = "preparando el modelo de recorte"
            recortador.preparar()
        except ErrorRecorte as error:
            self._modelo_fallido(str(error))
            return None
        except Exception as error:
            registro.error("No se pudo preparar el modelo de recorte (%s)", type(error).__name__)
            self._modelo_fallido(MENSAJE_MODELO_NO_CARGA)
            return None

        with self._candado:
            self._recortador, self._modelo_recortador = recortador, eleccion.modelo
            self.modelo.estado, self.modelo.mensaje = "listo", None
            self.trabajos["recorte"].mensaje = None
            activos = recortador.proveedores_activos()
            if "CUDAExecutionProvider" in getattr(recortador, "pedidos", []) and "CUDAExecutionProvider" not in activos:
                self.modelo.nota = equipo.MENSAJE_NVIDIA_SIN_CUDA
        self._anotar_fallo_del_acelerador(recortador, eleccion.modelo)
        registro.info("Modelo de recorte listo: %s", eleccion.modelo)
        return recortador

    # --- La aceleración medida -----------------------------------------------------------------------------------

    def _anotar_fallo_del_acelerador(self, recortador: Recortador, modelo: str) -> None:
        """Si el acelerador elegido falló al usarlo, el recortador ya siguió con el procesador: aquí se deja anotado."""
        if not recortador.acelerador_fallido:
            return
        recortador.acelerador_fallido = False
        registro.info("La aceleración falló: el recorte sigue con el procesador")
        if self._aceleracion is not None:
            try:
                self._aceleracion.anotar_fallo(modelo)
            except OSError as fallo:
                registro.error("No se pudo guardar la medición (%s)", type(fallo).__name__)

    def _medir_si_toca(self) -> None:
        """Al terminar un lote, con la cola vacía: prueba el acelerador una sola vez por modelo, sin parar nada."""
        aceleracion = self._aceleracion
        with self._candado:
            modelo = self._modelo_recortador
            tiempos = list(self._tiempos_modelo.get(modelo or "", []))
            libre = not (self._midiendo or self._cerrado or self._pendientes)
        toca = False
        try:
            toca = bool(aceleracion and libre and modelo and tiempos and aceleracion.hay_que_medir(modelo))
        finally:
            with self._hay_trabajo:
                self._por_medir = False
                self._midiendo = self._midiendo or toca
                self._hay_trabajo.notify_all()
        if toca:
            threading.Thread(
                target=self._medir, args=(modelo, statistics.median(tiempos)), name="medicion-aceleracion", daemon=True
            ).start()

    def _medir(self, modelo: str, segundos_procesador: float) -> None:
        elegido = None
        try:
            medida = self._aceleracion.medir(modelo, segundos_procesador)
            if medida is not None:
                elegido = medida["elegido"]
                registro.info("Aceleración medida para %s: se usa %s", modelo, elegido)
        except Exception as fallo:
            registro.error("No se pudo medir la aceleración (%s)", type(fallo).__name__)
        finally:
            with self._hay_trabajo:
                self._midiendo = False
                if elegido not in (None, "procesador"):
                    self._renovar_recortador = True
                self._hay_trabajo.notify_all()

    def esperar_medicion(self, segundos: float = 150.0) -> bool:
        """Espera a que termine la medición de la aceleración (para las pruebas). Devuelve si terminó a tiempo."""
        limite = time.monotonic() + segundos
        with self._hay_trabajo:
            while self._midiendo or self._por_medir:
                resto = limite - time.monotonic()
                if resto <= 0:
                    return False
                self._hay_trabajo.wait(timeout=min(resto, 0.2))
        return True

    def _avance_descarga(self, bytes_bajados: int) -> None:
        with self._candado:
            self.modelo.descargado_mb = min(self.modelo.total_mb, bytes_bajados // 1_000_000)

    def _modelo_fallido(self, mensaje: str) -> None:
        with self._candado:
            self.modelo.estado, self.modelo.mensaje = "error", mensaje
            self.trabajos["recorte"].mensaje = mensaje
            self._modelo_bloqueado = True

    # --- Ajustes y clave -----------------------------------------------------------------------------------------

    def cambiar_ajustes(self, cambios: object) -> None:
        """Guarda en `ajustes.json` la marca, la calidad del recorte, el modelo de escenas y el tope (nunca la clave)."""
        try:
            with self._candado:
                nuevos = los_ajustes.aplicar(self.ajustes, cambios)
                los_ajustes.guardar(self.config.ajustes, nuevos)
                self.ajustes = nuevos
        except los_ajustes.ErrorAjustes as error:
            raise ErrorEstudio(str(error))
        if nuevos["calidad_recorte"] != self.calidad_recorte:
            self.cambiar_calidad(nuevos["calidad_recorte"])

    def guardar_logo(self, origen: Path) -> None:
        try:
            los_ajustes.guardar_logo(origen, self.config.logo)
        except los_ajustes.ErrorAjustes as error:
            raise ErrorEstudio(str(error))

    def quitar_logo(self) -> None:
        self.config.logo.unlink(missing_ok=True)

    def guardar_clave(self, clave: object) -> None:
        """Escribe la clave en `.env`. Desde aquí no vuelve a salir entera."""
        try:
            la_clave.guardar(self.config.env, clave)
        except la_clave.ErrorClave as error:
            raise ErrorEstudio(str(error))
        registro.info("Clave de OpenRouter guardada")

    def borrar_clave(self) -> None:
        la_clave.borrar(self.config.env)

    def clave(self) -> str | None:
        """La clave, leída del `.env` en este momento. Solo para llamar a OpenRouter: nunca para mostrarla."""
        return la_clave.leer(self.config.env)

    def _clave_publica(self) -> dict:
        clave = self.clave()
        return {"guardada": clave is not None, "mascara": la_clave.mascara(clave) if clave else None}

    def _negocio_publico(self) -> dict:
        negocio = dict(self.ajustes["negocio"])
        negocio["sobre_principal"] = los_ajustes.color_sobre(negocio["color_principal"])
        negocio["sobre_acento"] = los_ajustes.color_sobre(negocio["color_acento"])
        try:
            negocio["logo"] = f"/api/logo?v={self.config.logo.stat().st_mtime_ns}"
        except OSError:
            negocio["logo"] = None
        return negocio

    # --- Fotos ---------------------------------------------------------------------------------------------------

    def agregar_foto(self, origen: Path, nombre_original: str) -> dict:
        """Comprueba una foto recién subida (ya guardada en `origen`) y, si vale, la pone en la cola de recorte.

        Devuelve lo que la página muestra para ese archivo: aceptada (con aviso o sin él) o el error.
        """
        nombre_limpio = limpiar_nombre(nombre_original)
        identificador = uuid.uuid4().hex[:12]
        carpeta = self.config.trabajo / identificador
        carpeta.mkdir(parents=True)
        original = carpeta / "original"
        shutil.move(str(origen), original)
        try:
            valida = validar(original)
            archivo = f"{nombre_limpio}.{EXTENSIONES[valida.tipo]}"
            foto = Foto(
                id=identificador, nombre=nombre_limpio, archivo=archivo, ancho=valida.ancho, alto=valida.alto,
                carpeta=carpeta, original=original, aviso=valida.aviso,
            )
            _guardar_vista(abrir_normalizada(original), foto.vista, "JPEG")
        except ErrorFoto as error:
            shutil.rmtree(carpeta, ignore_errors=True)
            return {"archivo": _nombre_para_mostrar(nombre_original), "aceptada": False, "error": str(error)}
        except Exception as error:
            registro.error("No se pudo abrir una foto subida (%s)", type(error).__name__)
            shutil.rmtree(carpeta, ignore_errors=True)
            return {
                "archivo": _nombre_para_mostrar(nombre_original),
                "aceptada": False,
                "error": "No se puede abrir esta foto: puede estar dañada.",
            }

        with self._hay_trabajo:
            foto.nombre = self._nombre_unico(foto.nombre)
            foto.archivo = f"{foto.nombre}.{EXTENSIONES[valida.tipo]}"
            self.fotos[foto.id] = foto
            self._encolar(foto.id)
        return {"id": foto.id, "archivo": foto.archivo, "aceptada": True, "aviso": foto.aviso}

    def _nombre_unico(self, nombre: str) -> str:
        usados = {foto.nombre for foto in self.fotos.values()}
        candidato, n = nombre, 2
        while candidato in usados:
            candidato, n = f"{nombre}-{n}", n + 1
        return candidato

    def _encolar(self, foto_id: str) -> None:
        trabajo = self.trabajos["recorte"]
        if trabajo.estado != "trabajando":
            trabajo.empezar()
            if self.modelo.estado == "error":
                trabajo.mensaje = self.modelo.mensaje
        trabajo.total += 1
        self._pendientes.append(foto_id)
        if self._hilo_recorte is None or not self._hilo_recorte.is_alive():
            self._hilo_recorte = threading.Thread(target=self._bucle_recorte, name="cola-recorte", daemon=True)
            self._hilo_recorte.start()
        self._hay_trabajo.notify_all()

    def quitar_foto(self, foto_id: str) -> None:
        """Quita una foto de la lista. Sus resultados ya creados se quedan en `salidas/`."""
        with self._hay_trabajo:
            foto = self.fotos.get(foto_id)
            if foto is None:
                raise ErrorEstudio("Esa foto ya no está en la lista.", 404)
            if foto.estado == "recortando":
                raise ErrorEstudio("Esta foto se está recortando: espera a que termine para quitarla.", 409)
            if foto.estado == "en_cola" and foto_id in self._pendientes:
                self._pendientes.remove(foto_id)
                trabajo = self.trabajos["recorte"]
                trabajo.total = max(trabajo.hechos, trabajo.total - 1)
                if trabajo.estado == "trabajando" and not self._pendientes and trabajo.actual is None:
                    trabajo.terminar()
            del self.fotos[foto_id]
        shutil.rmtree(foto.carpeta, ignore_errors=True)

    def empezar_de_nuevo(self) -> None:
        """Vacía la lista de fotos y abre una carpeta de resultados nueva. No borra nada de `salidas/`."""
        with self._hay_trabajo:
            if any(trabajo.estado == "trabajando" for trabajo in self.trabajos.values()):
                raise ErrorEstudio("Hay un trabajo en marcha: espera a que termine para empezar de nuevo.", 409)
            carpetas = [foto.carpeta for foto in self.fotos.values()]
            self.fotos.clear()
            self._pendientes.clear()
            for tipo in self.trabajos:
                self.trabajos[tipo] = Trabajo(tipo)
            self._nueva_sesion()
        for carpeta in carpetas:
            shutil.rmtree(carpeta, ignore_errors=True)

    def foto(self, foto_id: str) -> Foto:
        with self._candado:
            foto = self.fotos.get(foto_id)
        if foto is None:
            raise ErrorEstudio("Esa foto ya no está en la lista.", 404)
        return foto

    # --- La cola de recorte --------------------------------------------------------------------------------------

    def _bucle_recorte(self) -> None:
        while True:
            with self._hay_trabajo:
                while not self._cerrado and (not self._pendientes or self._modelo_bloqueado):
                    self._hay_trabajo.wait(timeout=1.0)
                if self._cerrado:
                    return
            recortador = self._asegurar_recortador()
            if recortador is None:
                continue  # la descarga falló: la cola espera al botón de reintentar
            with self._hay_trabajo:
                if not self._pendientes:
                    continue
                foto = self.fotos.get(self._pendientes.popleft())
                if foto is None:
                    continue
                foto.estado = "recortando"
                self.trabajos["recorte"].empezar_archivo(foto.archivo)
            self._recortar_foto(foto, recortador)

    def _recortar_foto(self, foto: Foto, recortador: Recortador) -> None:
        """Recorta una foto. Un fallo se queda en esa foto: el lote sigue."""
        inicio = time.monotonic()
        error = None
        try:
            resultado = recortar(abrir_normalizada(foto.original), recortador)
            destino = self.carpeta_salidas / "recortes" / f"{foto.nombre}_recorte.png"
            destino.parent.mkdir(parents=True, exist_ok=True)
            resultado.imagen.save(destino, "PNG", compress_level=4)
            _guardar_vista(resultado.imagen, foto.vista_recorte, "WEBP")
        except ErrorRecorte as fallo:
            error = str(fallo)
        except Exception as fallo:
            registro.error("No se pudo recortar una foto (%s)", type(fallo).__name__)
            error = MENSAJE_RECORTE_FALLIDO

        with self._hay_trabajo:
            foto.segundos = time.monotonic() - inicio
            if error:
                foto.estado, foto.error = "error", error
            else:
                foto.estado, foto.error = "lista", None
                foto.recorte, foto.cobertura = destino, resultado.cobertura
                izquierda, arriba, derecha, abajo = resultado.caja
                foto.porcentaje = max((derecha - izquierda) / foto.ancho, (abajo - arriba) / foto.alto) * 100
                foto.peso_recorte = destino.stat().st_size
                if not recortador.acelerado() and not recortador.acelerador_fallido:
                    # Lo que tarda el modelo con el procesador: con esto se compara el acelerador.
                    self._tiempos_modelo.setdefault(self._modelo_recortador or "", []).append(resultado.segundos_modelo)
            trabajo = self.trabajos["recorte"]
            trabajo.terminar_archivo(error)
            terminado = not self._pendientes
            if terminado:
                trabajo.terminar()
                self._por_medir = self._aceleracion is not None
            self._hay_trabajo.notify_all()
        self._anotar_fallo_del_acelerador(recortador, self._modelo_recortador or recortador.modelo)
        if terminado:
            self._medir_si_toca()

    def esperar(self, tipo: str, segundos: float = 60.0) -> bool:
        """Espera a que termine un trabajo (para las pruebas). Devuelve si terminó a tiempo."""
        limite = time.monotonic() + segundos
        with self._hay_trabajo:
            while self.trabajos[tipo].estado == "trabajando":
                resto = limite - time.monotonic()
                if resto <= 0:
                    return False
                self._hay_trabajo.wait(timeout=min(resto, 0.2))
        return True

    # --- Fondo blanco y medidas ----------------------------------------------------------------------------------

    def plataformas(self) -> list[Plataforma]:
        """Las plataformas de `plataformas.json`, leídas en el momento (el usuario puede editar el archivo)."""
        try:
            return cargar_plataformas(self.config.plataformas)
        except ErrorPlataformas as error:
            raise ErrorEstudio(str(error), 409)

    def generar_medidas(self, ids_fotos: list[str], ids_plataformas: list[str]) -> int:
        """Empieza el lote de fondo blanco y medidas. Devuelve cuántos archivos se van a crear."""
        elegidas = [p for p in self.plataformas() if p.id in set(ids_plataformas)]
        if not elegidas:
            raise ErrorEstudio("Elige al menos una plataforma.")
        with self._hay_trabajo:
            fotos = [self.fotos[i] for i in dict.fromkeys(ids_fotos) if i in self.fotos and self.fotos[i].estado == "lista"]
            if not fotos:
                raise ErrorEstudio("Elige al menos una foto ya recortada.")
            trabajo = self.trabajos["medidas"]
            if trabajo.estado == "trabajando":
                raise ErrorEstudio("Ya se están generando las medidas: espera a que terminen.", 409)
            trabajo.empezar(total=len(fotos) * len(elegidas))
            carpeta = self.carpeta_salidas
        threading.Thread(target=self._hacer_medidas, args=(fotos, elegidas, carpeta), name="medidas", daemon=True).start()
        return len(fotos) * len(elegidas)

    def _hacer_medidas(self, fotos: list[Foto], plataformas: list[Plataforma], carpeta: Path) -> None:
        trabajo = self.trabajos["medidas"]
        for foto in fotos:
            recorte = None
            for plataforma in plataformas:
                with self._candado:
                    trabajo.empezar_archivo(f"{foto.nombre}_{plataforma.id}.jpg")
                error = None
                try:
                    if recorte is None:
                        with Image.open(foto.recorte) as abierto:
                            abierto.load()
                            recorte = abierto.convert("RGBA")
                    salida = exportar(recorte, foto.nombre, plataforma, carpeta / plataforma.id)
                except Exception as fallo:
                    registro.error("No se pudo crear un archivo de medidas (%s)", type(fallo).__name__)
                    error, salida = "No se pudo crear este archivo. Vuelve a generar las medidas.", None
                with self._hay_trabajo:
                    if salida is not None:
                        anterior = foto.salidas.get(plataforma.id)
                        if anterior is not None and anterior.ruta != salida.ruta:
                            anterior.ruta.unlink(missing_ok=True)  # la medida cambió: fuera el archivo viejo
                        foto.salidas[plataforma.id] = salida
                    trabajo.terminar_archivo(error)
        with self._hay_trabajo:
            trabajo.terminar()
            self._hay_trabajo.notify_all()

    # --- Escenas con IA ------------------------------------------------------------------------------------------

    def _cliente(self) -> Cliente:
        """El cliente de OpenRouter. La clave se lee del archivo en cada llamada."""
        return Cliente(self.config.openrouter_url, self.clave, dormir=self._dormir)

    def probar_clave(self) -> str:
        """El botón Probar: «Conexión correcta · límite 2,00 $ · usado 0,12 $». No gasta."""
        try:
            return self._cliente().probar().texto()
        except ErrorOpenRouter as error:
            raise ErrorEstudio(str(error), 409)

    def _pedido_escenas(self, ids_fotos: object, escena: object, formato: object, propia: object, color: object):
        """Lo que se va a pedir, ya comprobado: las fotos, el pedido y la estimación. No llama a internet."""
        try:
            pedido = las_escenas.preparar_pedido(escena, formato, propia, color)
        except las_escenas.ErrorEscena as error:
            raise ErrorEstudio(str(error))
        ids = ids_fotos if isinstance(ids_fotos, list) else []
        with self._candado:
            fotos = [
                self.fotos[i] for i in dict.fromkeys(i for i in ids if isinstance(i, str))
                if i in self.fotos and self.fotos[i].estado == "lista"
            ]
            modelo = self.ajustes["modelo_escenas"]
        if not fotos:
            raise ErrorEstudio("Elige al menos una foto ya recortada.")
        return fotos, pedido, costos.estimar(self.config.gastos, modelo, len(fotos))

    def estimar_escenas(
        self, ids_fotos: object, escena: object, formato: object, propia: object = None, color: object = None
    ) -> dict:
        """El costo estimado, para mostrarlo antes de gastar. No gasta ni llama a internet."""
        fotos, _pedido, estimacion = self._pedido_escenas(ids_fotos, escena, formato, propia, color)
        mensaje = None
        if self.clave() is None:
            mensaje = MENSAJES_OPENROUTER["sin_clave"]
        else:
            with self._candado:
                tope, gastado = self.ajustes["tope_sesion_usd"], self.gasto_sesion
            try:
                costos.comprobar_tope(estimacion.total, tope, gastado)
            except costos.SinPresupuesto as error:
                mensaje = str(error)
        return {
            "imagenes": estimacion.imagenes,
            "modelo": estimacion.modelo,
            "costo_estimado_usd": estimacion.total,
            "costo_estimado": costos.dolares(estimacion.total),
            "texto": estimacion.texto(),
            "se_puede": mensaje is None,
            "mensaje": mensaje,
        }

    def generar_escenas(
        self,
        ids_fotos: object,
        escena: object,
        formato: object,
        propia: object = None,
        color: object = None,
        *,
        confirmado: object = False,
        costo_visto: object = None,
    ) -> dict:
        """Empieza el lote de escenas. Gasta dinero: solo con la confirmación y con el costo que vio el usuario."""
        if confirmado is not True:
            raise ErrorEstudio(MENSAJE_SIN_CONFIRMAR)
        fotos, pedido, estimacion = self._pedido_escenas(ids_fotos, escena, formato, propia, color)
        visto = costo_visto if isinstance(costo_visto, (int, float)) and not isinstance(costo_visto, bool) else None
        if visto is None or abs(visto - estimacion.total) > 0.0005:
            raise ErrorEstudio(
                f"El costo estimado ahora es {costos.dolares(estimacion.total)}. Míralo y confírmalo de nuevo.", 409
            )
        if self.clave() is None:
            raise ErrorEstudio(MENSAJES_OPENROUTER["sin_clave"])
        with self._candado:
            if self.trabajos["escenas"].estado == "trabajando":
                raise ErrorEstudio("Ya se están generando escenas: espera a que terminen.", 409)
            tope, gastado = self.ajustes["tope_sesion_usd"], self.gasto_sesion
        cliente = self._cliente()
        try:
            # Primero el tope de la sesión (si se supera, no se llama a OpenRouter); después, lo que queda en la clave.
            costos.antes_de_gastar(estimacion.total, tope, gastado, cliente.probar)
        except (costos.SinPresupuesto, ErrorOpenRouter) as error:
            raise ErrorEstudio(str(error), 409)

        with self._hay_trabajo:
            trabajo = self.trabajos["escenas"]
            if trabajo.estado == "trabajando":
                raise ErrorEstudio("Ya se están generando escenas: espera a que terminen.", 409)
            trabajo.empezar(total=len(fotos))
            trabajo.extra = self._costos_del_lote(estimacion.total, 0.0, 0, False)
            carpeta = self.carpeta_salidas / "escenas"
        threading.Thread(
            target=self._hacer_escenas, args=(fotos, pedido, estimacion, cliente, carpeta), name="escenas", daemon=True
        ).start()
        return {"imagenes": len(fotos), "costo_estimado": costos.dolares(estimacion.total)}

    @staticmethod
    def _costos_del_lote(estimado: float, real: float, hechas: int, sin_informar: bool) -> dict:
        return {
            "hechas": hechas,
            "costo_estimado_usd": estimado,
            "costo_estimado": costos.dolares(estimado),
            "costo_real_usd": round(real, 6),
            "costo_real": costos.dolares(real),
            "costo_sin_informar": sin_informar,  # OpenRouter no dijo el costo de alguna escena: se cuenta el estimado
        }

    def _hacer_escenas(self, fotos: list[Foto], pedido, estimacion, cliente: Cliente, carpeta: Path) -> None:
        trabajo = self.trabajos["escenas"]
        real, hechas, sin_informar, detenido = 0.0, 0, False, None

        def al_esperar(mensaje: str) -> None:
            with self._candado:
                trabajo.mensaje = mensaje

        for foto in fotos:
            with self._candado:
                trabajo.empezar_archivo(f"{foto.nombre}_escena_{pedido.escena}")
                tope, gastado = self.ajustes["tope_sesion_usd"], self.gasto_sesion
            error, escena = None, None
            try:
                # El tope se vuelve a mirar antes de cada imagen: los costos reales pueden ir por encima del estimado.
                costos.comprobar_tope(estimacion.por_imagen, tope, gastado)
                with Image.open(foto.recorte) as abierto:
                    abierto.load()
                    referencia = las_escenas.imagen_referencia(abierto.convert("RGBA"))
                imagen = cliente.generar(estimacion.modelo, pedido.texto, pedido.formato, referencia, al_esperar)
            except costos.SinPresupuesto as fallo:
                error = detenido = str(fallo)
            except ErrorOpenRouter as fallo:
                error = str(fallo)
                if fallo.posible_cobro:
                    with self._candado:
                        self.gasto_sesion += estimacion.por_imagen  # no sabemos si se cobró: cuenta para el tope
                if fallo.detiene_el_lote:
                    detenido = error
            except Exception as fallo:
                registro.error("No se pudo preparar una escena (%s)", type(fallo).__name__)
                error = MENSAJE_ESCENA_FALLIDA
            else:
                # Desde aquí la escena ya está cobrada: el gasto se anota pase lo que pase al guardarla.
                costo = imagen.costo
                contado = estimacion.por_imagen if costo is None else costo
                sin_informar = sin_informar or costo is None
                try:
                    costos.anotar_gasto(self.config.gastos, estimacion.modelo, estimacion.por_imagen, costo)
                except OSError as fallo:
                    registro.error("No se pudo anotar un gasto (%s)", type(fallo).__name__)
                real += contado
                with self._candado:
                    self.gasto_sesion += contado
                try:
                    escena = las_escenas.guardar(
                        imagen.datos, pedido, foto.nombre, carpeta,
                        modelo=estimacion.modelo, costo=costo, costo_estimado=estimacion.por_imagen,
                    )
                    hechas += 1
                except Exception as fallo:
                    registro.error("No se pudo guardar una escena (%s)", type(fallo).__name__)
                    error = MENSAJE_ESCENA_DANADA

            with self._hay_trabajo:
                if escena is not None:
                    foto.escenas.append(escena)
                trabajo.terminar_archivo(error)
                trabajo.extra = self._costos_del_lote(estimacion.total, real, hechas, sin_informar)
            if detenido:
                break

        with self._hay_trabajo:
            trabajo.terminar()
            if detenido:
                trabajo.mensaje = detenido
                trabajo.extra["detenido"] = True
            self._hay_trabajo.notify_all()

    def opciones(self) -> dict:
        """Lo que la página necesita para pintar sus listas: plataformas, escenas, formatos y modelos."""
        try:
            plataformas, error = [p.publica() for p in self.plataformas()], None
        except ErrorEstudio as fallo:
            plataformas, error = [], str(fallo)
        return {
            "plataformas": plataformas,
            "error_plataformas": error,
            "escenas": las_escenas.escenas_publicas(),
            "escena_propia": {"id": las_escenas.PROPIA, "maximo": las_escenas.PROPIA_MAXIMO},
            "escena_color": {"id": las_escenas.FONDO_LISO, "por_defecto": las_escenas.COLOR_POR_DEFECTO},
            "formatos": list(las_escenas.FORMATOS),
            "marca_escenas": las_escenas.MARCA_PAGINA,
            "nota_escenas": las_escenas.NOTA_PAGINA,
            "modelos_escenas": costos.modelos_publicos(),
            "calidades": [
                {"id": "automatica", "nombre": "Automática (recomendada)"},
                {"id": "maxima", "nombre": "Máxima"},
                {"id": "rapida", "nombre": "Rápida"},
            ],
            "subidas": {"max_fotos": MAX_FOTOS, "max_mb": MAX_MB},
        }

    # --- Archivos de resultados y descarga -----------------------------------------------------------------------

    def archivo(self, foto_id: str, nombre: str) -> Path:
        """La ruta de un archivo de resultados. Solo se sirven los que el propio estudio creó y tiene anotados."""
        with self._candado:
            foto = self.fotos.get(foto_id)
            conocidos = {} if foto is None else self._archivos_de(foto)
        ruta = conocidos.get(nombre)
        if ruta is None or not ruta.is_file():
            raise ErrorEstudio("Ese archivo no existe.", 404)
        return ruta

    def _archivos_de(self, foto: Foto) -> dict[str, Path]:
        archivos = {}
        if foto.recorte is not None:
            archivos[foto.recorte.name] = foto.recorte
        for salida in foto.salidas.values():
            archivos[salida.archivo] = salida.ruta
        for escena in foto.escenas:
            archivos[escena.archivo] = escena.ruta
        return archivos

    def descargar(self, filtro: str | None = None) -> Path:
        """Crea el ZIP de todo, o de una sola plataforma («recortes» y «escenas» también valen), con resumen.csv."""
        filtro = filtro or "todo"
        with self._candado:
            entradas = descargas.reunir(list(self.fotos.values()), self._orden_plataformas())
            sesion = self.sesion
        grupos = {entrada.grupo for entrada in entradas}
        if filtro != "todo":
            if filtro not in grupos and filtro not in {"recortes", "escenas", *self._orden_plataformas()}:
                raise ErrorEstudio("Esa plataforma no existe.", 404)
            entradas = [entrada for entrada in entradas if entrada.grupo == filtro]
        if not entradas:
            raise ErrorEstudio("Todavía no hay archivos para descargar.", 409)
        carpeta = self.config.trabajo / "descargas"
        carpeta.mkdir(parents=True, exist_ok=True)
        sufijo = "" if filtro == "todo" else f"_{filtro}"
        return descargas.crear_zip(entradas, carpeta / f"estudio-fotos_{sesion}{sufijo}.zip")

    def _orden_plataformas(self) -> list[str]:
        try:
            return [p.id for p in cargar_plataformas(self.config.plataformas)]
        except ErrorPlataformas:
            return []

    # --- Lo que ve la página -------------------------------------------------------------------------------------

    def _foto_publica(self, foto: Foto, orden: list[str]) -> dict:
        recorte = None
        if foto.recorte is not None:
            recorte = {
                "archivo": foto.recorte.name,
                "medida": f"{foto.ancho}×{foto.alto}",
                "peso": foto.peso_recorte,
                "peso_texto": descargas.texto_bytes(foto.peso_recorte),
                "url": f"/api/archivos/{foto.id}/{foto.recorte.name}",
            }
        return {
            "id": foto.id,
            "nombre": foto.nombre,
            "archivo": foto.archivo,
            "ancho": foto.ancho,
            "alto": foto.alto,
            "aviso": foto.aviso,
            "estado": foto.estado,
            "error": foto.error,
            "segundos": None if foto.segundos is None else round(foto.segundos, 1),
            "recorte": recorte,
            "salidas": [self._salida_publica(foto, salida) for salida in self._salidas_en_orden(foto, orden)],
            "escenas": [self._escena_publica(foto, escena) for escena in foto.escenas],
        }

    @staticmethod
    def _escena_publica(foto: Foto, escena) -> dict:
        return {
            "archivo": escena.archivo,
            "escena": escena.nombre_escena,
            "formato": escena.formato,
            "medida": f"{escena.ancho}×{escena.alto}",
            "peso": escena.peso,
            "peso_texto": descargas.texto_bytes(escena.peso),
            "costo": "sin informar" if escena.costo is None else costos.dolares(escena.costo),
            "marca": las_escenas.MARCA_PAGINA,
            "aviso": escena.aviso,
            "url": f"/api/archivos/{foto.id}/{escena.archivo}",
        }

    def _medicion_publica(self) -> str | None:
        """Lo que la página dice de la aceleración: que se está midiendo, o lo que salió."""
        if self._midiendo:
            return equipo.MENSAJE_MIDIENDO
        if self._aceleracion is None or not self.modelo.nombre:
            return None
        return self._aceleracion.texto(self.modelo.nombre)

    def _gasto_publico(self) -> dict:
        tope = self.ajustes["tope_sesion_usd"]
        return {
            "sesion_usd": round(self.gasto_sesion, 6),
            "sesion": costos.dolares(self.gasto_sesion),
            "tope": costos.dolares(tope),
            "queda": costos.dolares(max(0.0, tope - self.gasto_sesion)),
        }

    @staticmethod
    def _salidas_en_orden(foto: Foto, orden: list[str]) -> list[Salida]:
        puesto = {identificador: n for n, identificador in enumerate(orden)}
        return sorted(foto.salidas.values(), key=lambda salida: puesto.get(salida.plataforma, len(puesto)))

    @staticmethod
    def _salida_publica(foto: Foto, salida: Salida) -> dict:
        return {
            "plataforma": salida.plataforma,
            "nombre_plataforma": salida.nombre_plataforma,
            "archivo": salida.archivo,
            "medida": f"{salida.ancho}×{salida.alto}",
            "peso": salida.peso,
            "peso_texto": descargas.texto_bytes(salida.peso),
            "porcentaje": numero(salida.porcentaje, 0),
            "avisos": list(salida.avisos),
            "url": f"/api/archivos/{foto.id}/{salida.archivo}",
        }

    def publico(self) -> dict:
        """Todo el estado, tal como lo pinta la página."""
        orden = self._orden_plataformas()  # plataformas.json se lee una vez por consulta, no una por foto
        with self._candado:
            return {
                "herramienta": HERRAMIENTA,
                "version": VERSION,
                "aviso_puerto": self.aviso_puerto,
                "negocio": self._negocio_publico(),
                "ajustes": {
                    "calidad_recorte": self.ajustes["calidad_recorte"],
                    "modelo_escenas": self.ajustes["modelo_escenas"],
                    "tope_sesion_usd": self.ajustes["tope_sesion_usd"],
                    "tope_texto": costos.dolares(self.ajustes["tope_sesion_usd"]),
                },
                "clave": self._clave_publica(),
                "gasto": self._gasto_publico(),
                "modelo": {**self.modelo.publico(), "medicion": self._medicion_publica()},
                "trabajos": {tipo: trabajo.publico() for tipo, trabajo in self.trabajos.items()},
                "fotos": [self._foto_publica(foto, orden) for foto in self.fotos.values()],
            }


def _guardar_vista(imagen: Image.Image, destino: Path, formato: str) -> None:
    """Una copia pequeña para la página (el original no se toca)."""
    vista = imagen.copy()
    vista.info = {}  # sin los metadatos de la foto original
    vista.thumbnail((LADO_VISTA, LADO_VISTA), Image.Resampling.LANCZOS)
    if formato == "JPEG":
        vista.convert("RGB").save(destino, "JPEG", quality=85)
    else:
        vista.save(destino, "WEBP", quality=90, method=3)


def _nombre_para_mostrar(nombre_original: str) -> str:
    """El nombre del archivo rechazado, sin ruta y sin caracteres raros, para decir cuál fue."""
    base = (nombre_original or "").replace("\\", "/").split("/")[-1]
    extension = base.rsplit(".", 1)[-1] if "." in base else ""
    limpio = limpiar_nombre(base)
    extension = "".join(c for c in extension if c.isascii() and c.isalnum())[:5].lower()
    return f"{limpio}.{extension}" if extension else limpio
