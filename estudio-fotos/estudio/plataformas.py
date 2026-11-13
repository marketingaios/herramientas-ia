"""Lee y comprueba `plataformas.json`, que el usuario puede editar."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LADO_MINIMO = 100
LADO_MAXIMO = 10000


class ErrorPlataformas(Exception):
    """`plataformas.json` no se puede usar; el mensaje dice qué corregir."""


@dataclass(frozen=True)
class Plataforma:
    id: str
    nombre: str
    ancho: int
    alto: int
    porcentaje: float
    peso_maximo_kb: int | None = None
    sin_ampliar: bool = False
    ancho_minimo: int | None = None
    alto_minimo: int | None = None
    dice: str = ""
    fuente: str = ""

    @property
    def peso_maximo_bytes(self) -> int | None:
        """El máximo en bytes, con 1 KB = 1000 bytes (la lectura más estricta)."""
        return None if self.peso_maximo_kb is None else self.peso_maximo_kb * 1000

    def publica(self) -> dict:
        """Lo que ve la página."""
        if self.sin_ampliar and self.ancho_minimo and self.alto_minimo:
            medida = f"de {self.ancho_minimo}×{self.alto_minimo} a {self.ancho}×{self.alto}, sin ampliar"
        else:
            medida = f"{self.ancho}×{self.alto}"
        return {
            "id": self.id,
            "nombre": self.nombre,
            "medida": medida,
            "porcentaje": _numero(self.porcentaje),
            "peso_maximo": texto_peso(self.peso_maximo_kb),
            "dice": self.dice,
            "fuente": self.fuente,
        }


def texto_peso(kb: int | None) -> str:
    if kb is None:
        return "sin máximo publicado"
    if kb >= 1000:
        return f"{_numero(kb / 1000)} MB"
    return f"{kb} KB"


def _numero(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def cargar(ruta: Path) -> list[Plataforma]:
    """Lee las plataformas. Se llama cada vez que hacen falta: si el usuario edita el archivo, no hay que reiniciar."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErrorPlataformas("plataformas.json tiene un error: el archivo no existe. Recupéralo de la versión original.")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        donde = f" (línea {error.lineno})" if isinstance(error, json.JSONDecodeError) else ""
        raise ErrorPlataformas(
            f"plataformas.json tiene un error: no es un JSON válido{donde}. Corrígelo o vuelve a la versión original."
        )

    lista = datos.get("plataformas") if isinstance(datos, dict) else None
    if not isinstance(lista, list) or not lista:
        raise ErrorPlataformas("plataformas.json tiene un error: falta la lista «plataformas».")

    plataformas: list[Plataforma] = []
    vistas: set[str] = set()
    for posicion, item in enumerate(lista, start=1):
        plataforma = _leer_una(item, posicion)
        if plataforma.id in vistas:
            raise ErrorPlataformas(f"plataformas.json tiene un error: el id «{plataforma.id}» está repetido.")
        vistas.add(plataforma.id)
        plataformas.append(plataforma)
    return plataformas


def _leer_una(item: object, posicion: int) -> Plataforma:
    if not isinstance(item, dict):
        raise ErrorPlataformas(f"plataformas.json tiene un error: la plataforma {posicion} no es un objeto.")

    identificador = item.get("id")
    if not isinstance(identificador, str) or not _ID.fullmatch(identificador) or len(identificador) > 40:
        raise ErrorPlataformas(
            f"plataformas.json tiene un error: la plataforma {posicion} necesita un «id» en minúsculas, "
            "con letras, números o guiones."
        )
    quien = f"«{identificador}»"

    nombre = item.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        raise ErrorPlataformas(f"plataformas.json tiene un error: {quien} necesita un «nombre».")

    ancho = _lado(item.get("ancho"), "ancho", quien)
    alto = _lado(item.get("alto"), "alto", quien)

    porcentaje = item.get("porcentaje")
    if isinstance(porcentaje, bool) or not isinstance(porcentaje, (int, float)) or not 10 <= porcentaje <= 100:
        raise ErrorPlataformas(f"plataformas.json tiene un error: el «porcentaje» de {quien} debe estar entre 10 y 100.")

    peso = item.get("peso_maximo_kb")
    if peso is not None and (isinstance(peso, bool) or not isinstance(peso, int) or peso < 20):
        raise ErrorPlataformas(
            f"plataformas.json tiene un error: el «peso_maximo_kb» de {quien} debe ser un número entero "
            "(20 o más) o null."
        )

    sin_ampliar = item.get("sin_ampliar", False)
    if not isinstance(sin_ampliar, bool):
        raise ErrorPlataformas(f"plataformas.json tiene un error: «sin_ampliar» de {quien} debe ser true o false.")

    ancho_minimo = alto_minimo = None
    if sin_ampliar:
        ancho_minimo = _lado(item.get("ancho_minimo", ancho), "ancho_minimo", quien)
        alto_minimo = _lado(item.get("alto_minimo", alto), "alto_minimo", quien)
        if ancho_minimo > ancho or alto_minimo > alto:
            raise ErrorPlataformas(
                f"plataformas.json tiene un error: la medida mínima de {quien} no puede ser mayor que la medida."
            )

    return Plataforma(
        id=identificador,
        nombre=nombre.strip()[:80],
        ancho=ancho,
        alto=alto,
        porcentaje=float(porcentaje),
        peso_maximo_kb=peso,
        sin_ampliar=sin_ampliar,
        ancho_minimo=ancho_minimo,
        alto_minimo=alto_minimo,
        dice=str(item.get("dice", ""))[:400],
        fuente=str(item.get("fuente", ""))[:200],
    )


def _lado(valor: object, campo: str, quien: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or not LADO_MINIMO <= valor <= LADO_MAXIMO:
        raise ErrorPlataformas(
            f"plataformas.json tiene un error: «{campo}» de {quien} debe ser un número entero "
            f"entre {LADO_MINIMO} y {LADO_MAXIMO}."
        )
    return valor
