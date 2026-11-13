"""La descarga: un ZIP con los resultados y `resumen.csv`.

En el ZIP: `recortes/`, una carpeta por plataforma, `escenas/` y `resumen.csv` (archivo, plataforma, medida, peso,
porcentaje ocupado por el producto y avisos). Solo nombres de archivo: ninguna ruta del computador.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

COLUMNAS = ["archivo", "plataforma", "medida", "peso_kb", "porcentaje_producto", "avisos"]
AVISO_ESCENA = "hecha con IA: para redes y fotos secundarias"


@dataclass(frozen=True)
class Entrada:
    grupo: str  # «recortes», el id de la plataforma o «escenas»: la carpeta dentro del ZIP
    ruta: Path
    fila: dict


def texto_bytes(peso: int) -> str:
    """El peso de un archivo como se lee: «184 KB» o «1,2 MB» (1 KB = 1000 bytes)."""
    if peso >= 1_000_000:
        return f"{peso / 1_000_000:.1f}".replace(".", ",") + " MB"
    return f"{math.ceil(peso / 1000)} KB"


def _kb(peso: int) -> int:
    return math.ceil(peso / 1000)


def _porcentaje(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.1f}".replace(".", ",")


def reunir(fotos: list, orden_plataformas: list[str]) -> list[Entrada]:
    """Todos los archivos de resultados de la sesión, con su fila para el resumen."""
    orden = {identificador: n for n, identificador in enumerate(orden_plataformas)}
    entradas: list[Entrada] = []
    for foto in fotos:
        if foto.recorte is not None and foto.recorte.is_file():
            entradas.append(Entrada("recortes", foto.recorte, {
                "archivo": foto.recorte.name,
                "plataforma": "Recorte (PNG con transparencia)",
                "medida": f"{foto.ancho}x{foto.alto}",
                "peso_kb": _kb(foto.peso_recorte),
                "porcentaje_producto": _porcentaje(foto.porcentaje),
                "avisos": foto.aviso or "",
            }))
        for salida in sorted(foto.salidas.values(), key=lambda s: orden.get(s.plataforma, len(orden))):
            if salida.ruta.is_file():
                entradas.append(Entrada(salida.plataforma, salida.ruta, {
                    "archivo": salida.archivo,
                    "plataforma": salida.nombre_plataforma,
                    "medida": salida.medida,
                    "peso_kb": _kb(salida.peso),
                    "porcentaje_producto": _porcentaje(salida.porcentaje),
                    "avisos": " | ".join(salida.avisos),
                }))
        for escena in foto.escenas:
            if escena.ruta.is_file():
                entradas.append(Entrada("escenas", escena.ruta, {
                    "archivo": escena.archivo,
                    "plataforma": "Escena con IA",
                    "medida": f"{escena.ancho}x{escena.alto}",
                    "peso_kb": _kb(escena.peso),
                    "porcentaje_producto": "",
                    "avisos": AVISO_ESCENA,
                }))
    return entradas


def resumen_csv(entradas: list[Entrada]) -> bytes:
    """`resumen.csv` en UTF-8 con BOM (para que Excel lea bien los acentos), separado por comas."""
    memoria = io.StringIO(newline="")
    escritor = csv.DictWriter(memoria, fieldnames=COLUMNAS, lineterminator="\r\n")
    escritor.writeheader()
    for entrada in entradas:
        escritor.writerow(entrada.fila)
    return b"\xef\xbb\xbf" + memoria.getvalue().encode("utf-8")


def crear_zip(entradas: list[Entrada], destino: Path) -> Path:
    """Escribe el ZIP. Las fotos ya están comprimidas: se guardan tal cual, sin volver a comprimir."""
    temporal = destino.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_STORED) as archivo_zip:
        for entrada in entradas:
            archivo_zip.write(entrada.ruta, f"{entrada.grupo}/{entrada.ruta.name}")
        archivo_zip.writestr("resumen.csv", resumen_csv(entradas), compress_type=zipfile.ZIP_DEFLATED)
    temporal.replace(destino)
    return destino
