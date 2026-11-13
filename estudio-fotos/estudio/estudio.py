"""El estudio: las fotos de la sesión, la cola de recorte y los trabajos en lote.

Todo el estado vive en memoria, protegido con un candado. Una «sesión» va desde que arranca el servidor hasta que se
cierra; sus resultados quedan en `salidas/<fecha_hora>/`.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from . import HERRAMIENTA, VERSION, descargas, equipo
from .config import Config
from .encuadre import Salida, exportar
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
from .subidas import ErrorFoto, abrir_normalizada, limpiar_nombre, numero, validar

LADO_VISTA = 1400  # lado mayor de las vistas previas de la página
EXTENSIONES = {"jpeg": "jpg", "png": "png", "webp": "webp"}

MENSAJE_RECORTE_FALLIDO = "No se pudo recortar esta foto. Quítala y vuelve a subirla."
MENSAJE_MODELO_NO_CARGA = (
    "No se pudo preparar el modelo de recorte. Cierra otros programas para liberar memoria y vuelve a intentarlo."
)


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
    def __init__(self, config: Config, fabrica_recortador: Callable[[str], Recortador] | None = None) -> None:
        self.config = config
        self.config.preparar_carpetas()
        self._candado = threading.RLock()
        self._hay_trabajo = threading.Condition(self._candado)
        self._fabrica = fabrica_recortador or self._fabrica_por_defecto
        self._recortador: Recortador | None = None
        self._modelo_recortador: str | None = None
        self._modelo_bloqueado = False
        self._pendientes: deque[str] = deque()
        self._hilo_recorte: threading.Thread | None = None
        self._cerrado = False

        self.fotos: dict[str, Foto] = {}
        self.trabajos = {tipo: Trabajo(tipo) for tipo in ("recorte", "medidas", "escenas")}
        self.modelo = EstadoModelo()
        self.calidad_recorte = "automatica"
        self.aviso_puerto: str | None = None
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
        """Vacía los archivos temporales de una ejecución anterior. Se llama una vez, al arrancar."""
        for elemento in self.config.trabajo.iterdir():
            if elemento.is_dir():
                shutil.rmtree(elemento, ignore_errors=True)
            else:
                elemento.unlink(missing_ok=True)

    def cerrar(self) -> None:
        with self._hay_trabajo:
            self._cerrado = True
            self._hay_trabajo.notify_all()
        if self._hilo_recorte:
            self._hilo_recorte.join(timeout=10)

    # --- El modelo de recorte ------------------------------------------------------------------------------------

    def _fabrica_por_defecto(self, modelo: str) -> Recortador:
        if self.config.recortador == "simulado":
            return RecortadorSimulado()
        return RecortadorRembg(modelo, self.config.modelos, equipo.proveedores_para())

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
            if "CUDAExecutionProvider" in getattr(recortador, "proveedores", []) and "CUDAExecutionProvider" not in activos:
                self.modelo.nota = equipo.MENSAJE_NVIDIA_SIN_CUDA
        registro.info("Modelo de recorte listo: %s", eleccion.modelo)
        return recortador

    def _avance_descarga(self, bytes_bajados: int) -> None:
        with self._candado:
            self.modelo.descargado_mb = min(self.modelo.total_mb, bytes_bajados // 1_000_000)

    def _modelo_fallido(self, mensaje: str) -> None:
        with self._candado:
            self.modelo.estado, self.modelo.mensaje = "error", mensaje
            self.trabajos["recorte"].mensaje = mensaje
            self._modelo_bloqueado = True

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
            trabajo = self.trabajos["recorte"]
            trabajo.terminar_archivo(error)
            if not self._pendientes:
                trabajo.terminar()
            self._hay_trabajo.notify_all()

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

    def _foto_publica(self, foto: Foto) -> dict:
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
            "salidas": [self._salida_publica(foto, salida) for salida in self._salidas_en_orden(foto)],
        }

    def _salidas_en_orden(self, foto: Foto) -> list[Salida]:
        orden = {identificador: n for n, identificador in enumerate(self._orden_plataformas())}
        return sorted(foto.salidas.values(), key=lambda salida: orden.get(salida.plataforma, len(orden)))

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
        with self._candado:
            return {
                "herramienta": HERRAMIENTA,
                "version": VERSION,
                "aviso_puerto": self.aviso_puerto,
                "modelo": self.modelo.publico(),
                "trabajos": {tipo: trabajo.publico() for tipo, trabajo in self.trabajos.items()},
                "fotos": [self._foto_publica(foto) for foto in self.fotos.values()],
            }


def _guardar_vista(imagen: Image.Image, destino: Path, formato: str) -> None:
    """Una copia pequeña para la página (el original no se toca)."""
    vista = imagen.copy()
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
