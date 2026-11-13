"""La clave de OpenRouter: una línea en `herramientas-ia/.env`.

- Solo la escribe la página de Ajustes. Se cambia esa línea y las demás se dejan como están.
- Se lee del archivo cada vez que hace falta: si cambia, no hay que reiniciar.
- Nunca sale entera de aquí hacia la página: solo «••••» y sus 4 últimos caracteres.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

VARIABLE = "OPENROUTER_API_KEY"
MENSAJE_INVALIDA = "La clave no parece válida: cópiala entera, sin espacios."

_LINEA = re.compile(rf"^\s*(?:export\s+)?{VARIABLE}\s*=(.*)$")
_FORMA = re.compile(r"[A-Za-z0-9_.:\-]{8,400}")


class ErrorClave(Exception):
    """La clave no se puede guardar; el mensaje es para el usuario."""


def comprobar(clave: object) -> str:
    """La clave sin espacios alrededor, o un error si no tiene forma de clave."""
    if not isinstance(clave, str):
        raise ErrorClave(MENSAJE_INVALIDA)
    clave = clave.strip()
    if not _FORMA.fullmatch(clave):
        raise ErrorClave(MENSAJE_INVALIDA)
    return clave


def mascara(clave: str) -> str:
    """Cómo se ve la clave en la página: «••••» y sus 4 últimos caracteres."""
    return "••••" + clave[-4:]


def leer(ruta: Path) -> str | None:
    """La clave guardada, o None si no hay."""
    for linea in _lineas(ruta):
        encontrada = _LINEA.match(linea.rstrip("\r\n"))
        if encontrada:
            valor = encontrada.group(1).strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            return valor or None
    return None


def guardar(ruta: Path, clave: str) -> None:
    """Escribe la clave en su línea del `.env`. Las demás líneas no se tocan."""
    clave = comprobar(clave)
    lineas = _lineas(ruta)
    salto = "\r\n" if any(linea.endswith("\r\n") for linea in lineas) else "\n"
    nueva = f"{VARIABLE}={clave}{salto}"

    resultado, puesta = [], False
    for linea in lineas:
        if _LINEA.match(linea.rstrip("\r\n")):
            if not puesta:
                resultado.append(nueva)
                puesta = True
        else:
            resultado.append(linea)
    if not puesta:
        if resultado and not resultado[-1].endswith(("\n", "\r")):
            resultado[-1] += salto
        resultado.append(nueva)
    _escribir(ruta, resultado)


def borrar(ruta: Path) -> None:
    """Quita la línea de la clave. Si el archivo se queda vacío, se elimina."""
    lineas = _lineas(ruta)
    if not lineas:
        return
    resto = [linea for linea in lineas if not _LINEA.match(linea.rstrip("\r\n"))]
    if len(resto) == len(lineas):
        return
    if any(linea.strip() for linea in resto):
        _escribir(ruta, resto)
    else:
        Path(ruta).unlink(missing_ok=True)


def _lineas(ruta: Path) -> list[str]:
    try:
        with open(ruta, "r", encoding="utf-8", errors="surrogateescape", newline="") as archivo:
            return archivo.read().splitlines(keepends=True)
    except FileNotFoundError:
        return []


def _escribir(ruta: Path, lineas: list[str]) -> None:
    """Escritura de una vez (archivo temporal y cambio de nombre), legible solo por el usuario (permisos 600)."""
    ruta = Path(ruta)
    temporal = ruta.with_name(f"{ruta.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", errors="surrogateescape", newline="") as archivo:
            archivo.write("".join(lineas))
        os.replace(temporal, ruta)
    finally:
        if temporal.exists():
            temporal.unlink()
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass  # en Windows los permisos van por otro lado
