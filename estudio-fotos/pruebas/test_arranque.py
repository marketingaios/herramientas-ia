"""Paso 13: el arranque. `python -m estudio` elige puerto, escucha solo en 127.0.0.1, dice la dirección y abre el
navegador (salvo con `NO_ABRIR_NAVEGADOR=1`). El proceso se arranca de verdad, con los datos en una carpeta temporal.
"""

from __future__ import annotations

import os
import queue
import random
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
import pytest

import ayudas
from conftest import CARPETA
from estudio import __main__ as arranque


def _puerto_libre() -> int:
    """Un puerto libre cualquiera, con el siguiente también libre (para probar «usamos el N»).

    Lo elige la prueba, al azar entre 20000 y 60000: los que reparte el sistema pueden caer todos por encima de 60000,
    y la herramienta solo acepta `ESTUDIO_PUERTO` hasta 65000.
    """
    for _ in range(200):
        puerto = random.randrange(20000, 60000)
        try:
            with socket.socket() as uno, socket.socket() as dos:
                uno.bind(("127.0.0.1", puerto))
                dos.bind(("127.0.0.1", puerto + 1))
            return puerto
        except OSError:
            continue
    raise AssertionError("no hay puertos libres para la prueba")


class Proceso:
    """La herramienta arrancada como la arranca el usuario, pero con las variables de las pruebas."""

    def __init__(self, carpeta_datos, simulador, puerto: int, orden: list[str] | None = None, **entorno_extra) -> None:
        entorno = {k: v for k, v in os.environ.items() if not k.startswith("ESTUDIO_")}
        entorno.update(
            ESTUDIO_CARPETA_DATOS=str(carpeta_datos),
            ESTUDIO_OPENROUTER_URL=simulador.url,
            ESTUDIO_RECORTADOR="simulado",
            ESTUDIO_PUERTO=str(puerto),
            NO_ABRIR_NAVEGADOR="1",
            PYTHONUNBUFFERED="1",
            PYTHONIOENCODING="utf-8",
        )
        entorno.update(entorno_extra)
        for quitar in [k for k, v in entorno.items() if v is None]:
            del entorno[quitar]
        self.proceso = subprocess.Popen(
            [sys.executable, *(orden or ["-m", "estudio"])], cwd=CARPETA, env=entorno, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.lineas: list[str] = []
        self._cola: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._leer, daemon=True).start()

    def _leer(self) -> None:
        for linea in self.proceso.stdout:
            self._cola.put(linea.rstrip("\n"))

    def esperar_linea(self, empieza: str, segundos: float = 60) -> str:
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            try:
                linea = self._cola.get(timeout=0.2)
            except queue.Empty:
                if self.proceso.poll() is not None and self._cola.empty():
                    break
                continue
            self.lineas.append(linea)
            if linea.startswith(empieza):
                return linea
        raise AssertionError(f"no apareció «{empieza}…». Salida: {self.lineas}")

    def salida(self) -> str:
        while not self._cola.empty():
            self.lineas.append(self._cola.get())
        return "\n".join(self.lineas)

    def parar(self) -> int:
        if self.proceso.poll() is None:
            self.proceso.terminate()
            try:
                self.proceso.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proceso.kill()
                self.proceso.wait(timeout=5)
        return self.proceso.returncode


@pytest.fixture
def arrancar(carpeta_datos, simulador):
    procesos = []

    def _arrancar(puerto: int, orden: list[str] | None = None, **entorno) -> Proceso:
        proceso = Proceso(carpeta_datos, simulador, puerto, orden, **entorno)
        procesos.append(proceso)
        return proceso

    yield _arrancar
    for proceso in procesos:
        proceso.parar()


def _ip_de_la_red() -> str | None:
    """La dirección de este computador en la red local, si tiene (sin enviar nada a nadie)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("10.255.255.255", 1))  # en UDP esto solo elige la interfaz: no sale ningún paquete
            ip = sonda.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith("127.") else ip


# --- Elegir el puerto ---------------------------------------------------------------------------------------------------


def test_con_el_puerto_libre_se_usa_ese():
    puerto = _puerto_libre()
    enchufe, usado, aviso = arranque.elegir_puerto(puerto)
    try:
        assert (usado, aviso) == (puerto, None)
        assert enchufe.getsockname() == ("127.0.0.1", puerto)
    finally:
        enchufe.close()


def test_con_el_puerto_ocupado_se_usa_el_siguiente_y_se_dice():
    puerto = _puerto_libre()
    with socket.socket() as otro_programa:
        otro_programa.bind(("127.0.0.1", puerto))
        otro_programa.listen(1)
        enchufe, usado, aviso = arranque.elegir_puerto(puerto)
        try:
            assert usado == puerto + 1
            assert aviso == f"El puerto {puerto} está ocupado: usamos el {puerto + 1}."
        finally:
            enchufe.close()


def test_el_mensaje_del_puerto_es_el_de_la_ficha():
    assert arranque.mensaje_puerto_ocupado(8601, 8602) == "El puerto 8601 está ocupado: usamos el 8602."
    from estudio import config

    assert config.PUERTO == 8601 and arranque.ANFITRION == "127.0.0.1"


def test_el_puerto_de_partida_es_el_8601_salvo_en_las_pruebas(monkeypatch):
    from estudio import config

    monkeypatch.delenv("ESTUDIO_PUERTO", raising=False)
    assert config.puerto_inicial() == 8601
    monkeypatch.setenv("ESTUDIO_PUERTO", "8700")
    assert config.puerto_inicial() == 8700
    for raro in ("80", "abc", "99999", "-1", ""):
        monkeypatch.setenv("ESTUDIO_PUERTO", raro)
        assert config.puerto_inicial() == 8601


# --- El navegador -------------------------------------------------------------------------------------------------------


def test_abre_el_navegador_con_la_direccion(monkeypatch):
    abiertas = []
    monkeypatch.setattr(arranque.webbrowser, "open", lambda direccion: abiertas.append(direccion) or True)
    monkeypatch.delenv("NO_ABRIR_NAVEGADOR", raising=False)
    assert arranque.abrir_navegador("http://127.0.0.1:8601") is True
    assert abiertas == ["http://127.0.0.1:8601"]


def test_con_no_abrir_navegador_no_lo_abre(monkeypatch):
    abiertas = []
    monkeypatch.setattr(arranque.webbrowser, "open", lambda direccion: abiertas.append(direccion) or True)
    monkeypatch.setenv("NO_ABRIR_NAVEGADOR", "1")
    assert arranque.abrir_navegador("http://127.0.0.1:8601") is False
    assert abiertas == []


def test_sin_navegador_no_se_rompe(monkeypatch):
    def falla(direccion):
        raise RuntimeError("no hay navegador")

    monkeypatch.setattr(arranque.webbrowser, "open", falla)
    monkeypatch.delenv("NO_ABRIR_NAVEGADOR", raising=False)
    assert arranque.abrir_navegador("http://127.0.0.1:8601") is False


# --- El proceso de verdad -----------------------------------------------------------------------------------------------


def test_arranca_escribe_la_direccion_y_responde_solo_en_este_computador(arrancar, carpeta_datos):
    puerto = _puerto_libre()
    proceso = arrancar(puerto)
    linea = proceso.esperar_linea("Estudio de fotos abierto en ")
    assert linea == f"Estudio de fotos abierto en http://127.0.0.1:{puerto}"

    with httpx.Client(trust_env=False, timeout=10) as cliente:
        estado = cliente.get(f"http://127.0.0.1:{puerto}/api/estado")
        assert estado.status_code == 200 and estado.json()["aviso_puerto"] is None
        assert "server" not in estado.headers  # no dice qué programa lo sirve
        assert cliente.get(f"http://127.0.0.1:{puerto}/docs").status_code == 404

    # No escucha en la red local ni por IPv6: solo en 127.0.0.1.
    ip = _ip_de_la_red()
    if ip:
        with pytest.raises(OSError):
            socket.create_connection((ip, puerto), timeout=2).close()
    with pytest.raises(OSError):
        socket.create_connection(("::1", puerto), timeout=2).close()

    # Los datos de esta ejecución fueron a la carpeta temporal.
    assert (carpeta_datos / "estudio-fotos" / "trabajo").is_dir() and (carpeta_datos / "estudio-fotos" / "salidas").is_dir()

    assert proceso.parar() is not None
    salida = proceso.salida()
    assert "Traceback" not in salida and str(carpeta_datos) not in salida


def test_al_arrancar_se_quita_la_marca_del_negocio_que_dejo_la_version_1(arrancar, carpeta_datos):
    """La herramienta de verdad, sobre una carpeta de datos de la versión 1 (en la carpeta temporal)."""
    import json

    datos = carpeta_datos / "estudio-fotos"
    datos.mkdir(parents=True, exist_ok=True)
    los_tres = {"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5}
    marca = {"nombre": "Mi tienda de prueba", "color_principal": "#123456", "color_acento": "#ABCDEF"}
    (datos / "ajustes.json").write_text(json.dumps({"negocio": marca, **los_tres}, ensure_ascii=False), encoding="utf-8")
    (datos / "logo_negocio.png").write_bytes(ayudas.foto(600, 200, "PNG"))
    (datos / "gastos.jsonl").write_text('{"ts": "2026-11-13T21:56:33Z", "imagenes": 1}\n', encoding="utf-8")

    puerto = _puerto_libre()
    proceso = arrancar(puerto)
    proceso.esperar_linea("Estudio de fotos abierto en ")
    assert json.loads((datos / "ajustes.json").read_text(encoding="utf-8")) == los_tres
    assert not (datos / "logo_negocio.png").exists()
    assert (datos / "gastos.jsonl").read_text(encoding="utf-8") == '{"ts": "2026-11-13T21:56:33Z", "imagenes": 1}\n'
    with httpx.Client(trust_env=False, timeout=10) as cliente:
        estado = cliente.get(f"http://127.0.0.1:{puerto}/api/estado")
        assert estado.json()["ajustes"] == {**los_tres, "tope_texto": "2,50 $"}
        assert "negocio" not in estado.json() and "Mi tienda" not in estado.text
        assert cliente.get(f"http://127.0.0.1:{puerto}/api/logo").status_code == 404

    proceso.parar()
    salida = proceso.salida()
    for resto in ("Mi tienda", "#123456", "negocio", "logo", "Traceback", str(carpeta_datos)):
        assert resto not in salida, resto


def test_con_el_puerto_ocupado_el_proceso_usa_el_siguiente_y_lo_dice(arrancar):
    puerto = _puerto_libre()
    with socket.socket() as otro_programa:
        otro_programa.bind(("127.0.0.1", puerto))
        otro_programa.listen(1)
        proceso = arrancar(puerto)
        aviso = proceso.esperar_linea("El puerto ")
        assert aviso == f"El puerto {puerto} está ocupado: usamos el {puerto + 1}."
        linea = proceso.esperar_linea("Estudio de fotos abierto en ")
        assert linea == f"Estudio de fotos abierto en http://127.0.0.1:{puerto + 1}"
        with httpx.Client(trust_env=False, timeout=10) as cliente:
            estado = cliente.get(f"http://127.0.0.1:{puerto + 1}/api/estado").json()
        assert estado["aviso_puerto"] == aviso  # la página también lo dice


def test_dos_copias_a_la_vez_no_se_pisan(arrancar):
    puerto = _puerto_libre()
    primera = arrancar(puerto)
    primera.esperar_linea("Estudio de fotos abierto en ")
    segunda = arrancar(puerto)
    assert segunda.esperar_linea("Estudio de fotos abierto en ") == f"Estudio de fotos abierto en http://127.0.0.1:{puerto + 1}"
    with httpx.Client(trust_env=False, timeout=10) as cliente:
        assert cliente.get(f"http://127.0.0.1:{puerto}/api/estado").status_code == 200
        assert cliente.get(f"http://127.0.0.1:{puerto + 1}/api/estado").status_code == 200


@pytest.mark.parametrize("falta", ["ESTUDIO_CARPETA_DATOS", "ESTUDIO_OPENROUTER_URL"])
def test_con_las_variables_de_pruebas_a_medias_no_arranca(arrancar, falta):
    """La salvaguarda: carpeta temporal y simulador van juntos, o la herramienta no arranca."""
    puerto = _puerto_libre()
    proceso = arrancar(puerto, **{falta: None})
    assert proceso.proceso.wait(timeout=30) == 2
    salida = proceso.salida()
    assert "No se puede arrancar: Las variables de pruebas van juntas" in salida
    assert "Estudio de fotos abierto" not in salida and "Traceback" not in salida
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", puerto), timeout=1).close()


def test_un_simulador_fuera_de_este_computador_no_se_acepta(arrancar):
    proceso = arrancar(_puerto_libre(), ESTUDIO_OPENROUTER_URL="https://otro-servidor.example/api/v1")
    assert proceso.proceso.wait(timeout=30) == 2
    assert "debe apuntar a 127.0.0.1 o localhost" in proceso.salida()


# --- La consola y la carpeta de trabajo (revisión de seguridad) ---------------------------------------------------------

# El arranque de siempre, pero con la aplicación rota: un error que nadie controla, con una ruta personal dentro.
_ARRANQUE_ROTO = """
import sys
from pathlib import Path

import estudio.servidor as servidor


def rota(config):
    raise RuntimeError(f"no se pudo preparar {Path.home()}/algo")


servidor.crear_aplicacion = rota
from estudio.__main__ import main

sys.exit(main())
"""


def test_si_el_arranque_falla_la_consola_no_muestra_la_traza_ni_la_carpeta_personal(arrancar):
    from pathlib import Path

    puerto = _puerto_libre()
    proceso = arrancar(puerto, orden=["-c", _ARRANQUE_ROTO])
    assert proceso.proceso.wait(timeout=30) == 1
    salida = proceso.salida()
    assert "Error inesperado (RuntimeError, en <string>:" in salida and "Vuelve a abrir la herramienta" in salida
    assert "Traceback" not in salida and str(Path.home()) not in salida and "no se pudo preparar" not in salida
    assert "Estudio de fotos abierto" not in salida
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", puerto), timeout=1).close()


@pytest.mark.skipif(os.name == "nt", reason="en Windows, parar un proceso desde fuera no le deja cerrar con orden")
@pytest.mark.parametrize("senal", [signal.SIGINT, signal.SIGTERM], ids=["con Ctrl+C", "parado desde fuera"])
def test_al_cerrar_no_quedan_fotos_en_la_carpeta_de_trabajo(arrancar, carpeta_datos, senal):
    puerto = _puerto_libre()
    proceso = arrancar(puerto)
    proceso.esperar_linea("Estudio de fotos abierto en ")
    trabajo = carpeta_datos / "estudio-fotos" / "trabajo"

    with httpx.Client(base_url=f"http://127.0.0.1:{puerto}", trust_env=False, timeout=30) as cliente:
        subida = cliente.post("/api/fotos", files=[("fotos", ("bolsa.jpg", ayudas.foto(1024, 1024), "image/jpeg"))])
        assert subida.status_code == 200, subida.text
        limite = time.monotonic() + 30
        while not cliente.get("/api/estado").json()["fotos"][0].get("recorte"):
            assert time.monotonic() < limite, "el recorte no terminó"
            time.sleep(0.1)
    assert [p for p in trabajo.rglob("*") if p.is_file()], "la foto subida debería estar en trabajo/ mientras se usa"

    proceso.proceso.send_signal(senal)
    codigo = proceso.proceso.wait(timeout=30)
    salida = proceso.salida()
    if senal == signal.SIGINT:  # como lo cierra el usuario
        assert codigo == 0 and "Estudio de fotos cerrado." in salida
    assert "Traceback" not in salida
    assert [p for p in trabajo.rglob("*") if p.is_file()] == []  # ni la foto original ni sus vistas
    assert list((carpeta_datos / "estudio-fotos" / "salidas").rglob("*_recorte.png"))  # los resultados sí se quedan
