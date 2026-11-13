"""Arranque del estudio de fotos: `uv run --directory estudio-fotos python -m estudio`.

Escucha solo en este computador (127.0.0.1), a partir del puerto 8601. Si está ocupado usa el siguiente libre y lo
dice. Cuando el servidor responde, escribe la dirección y abre el navegador (salvo con `NO_ABRIR_NAVEGADOR=1`).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

from . import config as la_config
from . import registro as el_registro

ANFITRION = "127.0.0.1"  # solo este computador: nunca otra interfaz
INTENTOS = 50


def mensaje_puerto_ocupado(pedido: int, usado: int) -> str:
    return f"El puerto {pedido} está ocupado: usamos el {usado}."


def _alguien_escucha(puerto: int) -> bool:
    """¿Ya hay un programa atendiendo en ese puerto de este computador?"""
    try:
        with socket.create_connection((ANFITRION, puerto), timeout=0.3):
            return True
    except OSError:
        return False


def elegir_puerto(inicio: int) -> tuple[socket.socket, int, str | None]:
    """Reserva el primer puerto libre desde `inicio`. Devuelve el enchufe ya reservado, el puerto y el aviso."""
    for puerto in range(inicio, inicio + INTENTOS):
        if _alguien_escucha(puerto):
            continue
        enchufe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == "nt":
                enchufe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                enchufe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            enchufe.bind((ANFITRION, puerto))
        except OSError:
            enchufe.close()
            continue
        aviso = None if puerto == inicio else mensaje_puerto_ocupado(inicio, puerto)
        return enchufe, puerto, aviso
    raise RuntimeError(
        f"No hay ningún puerto libre entre el {inicio} y el {inicio + INTENTOS - 1}. "
        "Cierra otras herramientas y vuelve a intentarlo."
    )


def _responde(puerto: int) -> bool:
    """¿El servidor ya contesta? Se le pide el estado, sin salir de este computador."""
    try:
        with socket.create_connection((ANFITRION, puerto), timeout=2) as conexion:
            conexion.sendall(f"GET /api/estado HTTP/1.1\r\nHost: {ANFITRION}:{puerto}\r\nConnection: close\r\n\r\n".encode())
            return conexion.recv(64).startswith(b"HTTP/1.1 200")
    except OSError:
        return False


def abrir_navegador(direccion: str) -> bool:
    """Abre la página en el navegador, salvo que se pida que no (`NO_ABRIR_NAVEGADOR=1`)."""
    if os.environ.get("NO_ABRIR_NAVEGADOR", "").strip() == "1":
        return False
    try:
        return bool(webbrowser.open(direccion))
    except Exception:
        return False  # sin navegador (un servidor, por ejemplo): la dirección ya está escrita en la consola


def _anunciar(puerto: int, servidor) -> None:
    """Espera a que el servidor responda; entonces escribe la dirección y abre el navegador."""
    direccion = f"http://{ANFITRION}:{puerto}"
    limite = time.monotonic() + 60
    while time.monotonic() < limite and not servidor.should_exit:
        if servidor.started and _responde(puerto):
            print(f"Estudio de fotos abierto en {direccion}", flush=True)
            print("Para cerrarlo, pulsa Ctrl+C en esta ventana.", flush=True)
            abrir_navegador(direccion)
            return
        time.sleep(0.1)
    if not servidor.should_exit:
        print("El estudio de fotos no respondió al arrancar. Ciérralo (Ctrl+C) y vuelve a abrirlo.", flush=True)


def main() -> int:
    try:  # en Windows la consola puede no estar en UTF-8: los acentos y «…» no deben impedir arrancar
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    el_registro.preparar()

    try:
        config = la_config.desde_entorno()
        enchufe, puerto, aviso = elegir_puerto(la_config.puerto_inicial())
    except (ValueError, RuntimeError) as error:
        print(f"No se puede arrancar: {error}", file=sys.stderr, flush=True)
        return 2
    if aviso:
        print(aviso, flush=True)

    import uvicorn

    from .servidor import crear_aplicacion

    aplicacion = crear_aplicacion(config)
    aplicacion.state.estudio.aviso_puerto = aviso
    servidor = uvicorn.Server(
        uvicorn.Config(aplicacion, host=ANFITRION, port=puerto, log_level="warning", access_log=False, server_header=False)
    )
    el_registro.preparar()  # el filtro, también en los registros que uvicorn acaba de crear
    threading.Thread(target=_anunciar, args=(puerto, servidor), name="anuncio", daemon=True).start()
    try:
        servidor.run(sockets=[enchufe])  # el enchufe ya está reservado en 127.0.0.1
    except KeyboardInterrupt:
        pass
    finally:
        enchufe.close()
    print("Estudio de fotos cerrado.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
