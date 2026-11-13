"""Qué computador es, qué modelo de recorte le toca y qué es lo más rápido para usarlo.

- Mac con chip Apple, o PC con tarjeta NVIDIA: el modelo completo («Calidad máxima»).
- Los demás: el modelo ligero («Modo rápido»), y la página lo dice.
- La aceleración se mide, no se supone: en un Mac con chip Apple se prueba CoreML una sola vez por modelo, en un
  proceso aparte y con 2 minutos como máximo. Si falla, tarda demasiado o es más lenta, se sigue con el procesador.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

CALIDADES = ("automatica", "maxima", "rapida")
MODELO_COMPLETO = "birefnet-general"
MODELO_LIGERO = "birefnet-general-lite"

MENSAJE_MODO_RAPIDO = (
    "Modo rápido: tu computador no tiene aceleración y usamos un modelo más ligero. Puedes cambiarlo en Ajustes."
)
MENSAJE_NVIDIA_SIN_CUDA = (
    "La tarjeta NVIDIA no se pudo usar (pueden faltar CUDA o cuDNN): usamos el procesador, que es más lento. "
    "Puedes elegir «Rápida» en Ajustes."
)

PROCESADOR = ["CPUExecutionProvider"]
# Lo que pide la ficha para un Mac con chip Apple (rembg no usa CoreML por sí solo).
PROVEEDORES_COREML = [("CoreMLExecutionProvider", {"ModelFormat": "MLProgram"}), "CPUExecutionProvider"]
NOMBRE_COREML = "CoreML (MLProgram)"
TIEMPO_MAXIMO = 120  # segundos: lo que puede tardar la prueba del acelerador (preparar el modelo y recortar una foto)


@dataclass(frozen=True)
class Eleccion:
    modelo: str
    etiqueta: str  # «Calidad máxima» o «Modo rápido»
    nota: str | None = None  # lo que la página explica, si hace falta


def chip_apple() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def proveedores_disponibles() -> list[str]:
    """Los aceleradores que ofrece onnxruntime en este computador."""
    try:
        import onnxruntime

        return list(onnxruntime.get_available_providers())
    except Exception:
        return []


def tarjeta_nvidia() -> bool:
    """Hay tarjeta NVIDIA utilizable si se instaló la opción `gpu` y onnxruntime ofrece CUDA."""
    return "CUDAExecutionProvider" in proveedores_disponibles()


def elegir_modelo(calidad: str, *, apple: bool | None = None, nvidia: bool | None = None) -> Eleccion:
    """El modelo según el ajuste «Calidad del recorte» y, en Automática, según el computador."""
    if calidad == "maxima":
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    if calidad == "rapida":
        return Eleccion(MODELO_LIGERO, "Modo rápido")

    apple = chip_apple() if apple is None else apple
    if apple:
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    nvidia = tarjeta_nvidia() if nvidia is None else nvidia
    if nvidia:
        return Eleccion(MODELO_COMPLETO, "Calidad máxima")
    return Eleccion(MODELO_LIGERO, "Modo rápido", MENSAJE_MODO_RAPIDO)


def proveedores_para(*, apple: bool | None = None, nvidia: bool | None = None) -> list:
    """Con qué se crea la sesión de recorte de entrada: el procesador, o CUDA si hay tarjeta NVIDIA.

    En un Mac se empieza siempre con el procesador; CoreML solo se usa si la medición dice que es más rápido.
    """
    apple = chip_apple() if apple is None else apple
    if apple:
        return list(PROCESADOR)
    nvidia = tarjeta_nvidia() if nvidia is None else nvidia
    if nvidia:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return list(PROCESADOR)


# --- La aceleración medida ----------------------------------------------------------------------------------------

MENSAJE_MIDIENDO = (
    "Midiendo si la aceleración de tu computador es más rápida (una sola vez, 2 minutos como máximo). "
    "Puedes seguir trabajando."
)

MOTIVOS = {
    "mas_rapida": "La aceleración es más rápida que el procesador: se usa la aceleración.",
    "mas_lenta": "La aceleración funciona, pero el procesador es más rápido: se usa el procesador.",
    "fallo": "La aceleración falló al preparar el modelo: se usa el procesador.",
    "tiempo": "La aceleración tardó más de 2 minutos en preparar el modelo: se usa el procesador.",
    "sin_acelerador": "Este computador no ofrece aceleración para este modelo: se usa el procesador.",
    "fallo_al_usarla": "La aceleración dejó de funcionar al usarla: se usa el procesador.",
}


def _segundos(valor: float | None) -> str:
    return "" if valor is None else f"{valor:.1f}".replace(".", ",") + " s"


class Aceleracion:
    """La medición de la aceleración en este computador. Se guarda en `medicion.json`, una entrada por modelo.

    La prueba del acelerador corre en otro proceso: si se cuelga o tarda minutos (pasa con CoreML y BiRefNet), se
    corta al llegar al tiempo máximo y la herramienta sigue con el procesador, sin romper ningún lote.
    """

    def __init__(
        self,
        ruta: Path,
        carpeta_modelos: Path,
        carpeta_trabajo: Path,
        *,
        apple: bool | None = None,
        proveedores: list[str] | None = None,
        orden: list[str] | None = None,
        tiempo_maximo: float = TIEMPO_MAXIMO,
    ) -> None:
        self.ruta = Path(ruta)
        self.carpeta_modelos = Path(carpeta_modelos)
        self.carpeta_trabajo = Path(carpeta_trabajo)
        self._apple = apple
        self._proveedores = proveedores
        self._orden = orden  # las pruebas cambian el proceso que se lanza
        self.tiempo_maximo = tiempo_maximo
        self._candado = threading.Lock()
        self._proceso: subprocess.Popen | None = None
        self._cancelada = False
        self._leido: dict | None = None  # lo guardado se lee una vez: la página lo pregunta en cada consulta

    # Lo guardado

    def leer(self) -> dict:
        with self._candado:
            if self._leido is None:
                try:
                    datos = json.loads(self.ruta.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    datos = {}
                self._leido = datos if isinstance(datos, dict) else {}
            return dict(self._leido)

    def de(self, modelo: str) -> dict | None:
        medida = self.leer().get(modelo)
        return dict(medida) if isinstance(medida, dict) and medida.get("elegido") in ("procesador", "coreml") else None

    def _guardar(self, modelo: str, medida: dict) -> None:
        datos = self.leer()
        datos[modelo] = medida
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_name(self.ruta.name + ".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporal.replace(self.ruta)
        with self._candado:
            self._leido = datos

    # Qué usar

    def _hay_coreml(self) -> bool:
        apple = chip_apple() if self._apple is None else self._apple
        proveedores = proveedores_disponibles() if self._proveedores is None else self._proveedores
        return apple and "CoreMLExecutionProvider" in proveedores

    def hay_que_medir(self, modelo: str) -> bool:
        """Una sola vez por modelo, y solo donde hay un acelerador que probar."""
        return self._hay_coreml() and self.de(modelo) is None

    def proveedores_para(self, modelo: str) -> list:
        """El acelerador, si la medición dijo que es lo más rápido; si no, lo de siempre."""
        medida = self.de(modelo)
        if medida and medida["elegido"] == "coreml" and self._hay_coreml():
            self._temporales_dentro()
            return list(PROVEEDORES_COREML)
        return proveedores_para(apple=self._apple)

    def _temporales_dentro(self) -> None:
        """Si se va a usar el acelerador en este proceso, sus temporales también van dentro de `trabajo/`.

        Igual que en la prueba, que los manda a `trabajo/aceleracion`: nada se escribe fuera de la carpeta.
        """
        carpeta = self.carpeta_trabajo / "acelerador"
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        os.environ["TMPDIR"] = str(carpeta)

    def texto(self, modelo: str) -> str | None:
        """Lo medido, en una frase para la página."""
        medida = self.de(modelo)
        if not medida:
            return None
        motivo = MOTIVOS.get(medida.get("motivo"), "")
        if not isinstance(medida.get("procesador_s"), (int, float)):
            return motivo or None
        tiempos = f"Medido en este computador: {_segundos(medida['procesador_s'])} por foto con el procesador"
        if isinstance(medida.get("acelerador_s"), (int, float)):
            tiempos += f" y {_segundos(medida['acelerador_s'])} con {medida.get('acelerador') or 'la aceleración'}"
        return f"{tiempos}. {motivo}".strip()

    # La medición

    def medir(self, modelo: str, segundos_procesador: float) -> dict | None:
        """Prueba el acelerador con una foto, lo compara con el procesador y guarda con cuál se queda.

        Si la herramienta se cierra a mitad de la prueba, no se guarda nada: se medirá la próxima vez.
        """
        resultado = self._probar(modelo)
        estado, acelerador_s = resultado.get("estado"), resultado.get("segundos")
        if estado == "cancelada":
            return None
        if estado == "bien" and isinstance(acelerador_s, (int, float)) and not isinstance(acelerador_s, bool) and acelerador_s > 0:
            motivo = "mas_rapida" if acelerador_s < segundos_procesador else "mas_lenta"
        else:
            acelerador_s = None
            motivo = estado if estado in ("tiempo", "sin_acelerador") else "fallo"
        medida = {
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "acelerador": NOMBRE_COREML,
            "procesador_s": round(segundos_procesador, 2),
            "acelerador_s": None if acelerador_s is None else round(acelerador_s, 2),
            "preparar_s": resultado.get("preparar_s") if acelerador_s is not None else None,
            "elegido": "coreml" if motivo == "mas_rapida" else "procesador",
            "motivo": motivo,
        }
        self._guardar(modelo, medida)
        return medida

    def anotar_fallo(self, modelo: str) -> None:
        """La aceleración elegida falló al usarla de verdad: se vuelve al procesador y no se intenta más."""
        medida = self.de(modelo) or {"acelerador": NOMBRE_COREML, "procesador_s": None, "acelerador_s": None}
        medida.update(elegido="procesador", motivo="fallo_al_usarla")
        self._guardar(modelo, medida)

    def _probar(self, modelo: str) -> dict:
        """Lanza la prueba en otro proceso y la corta si pasa del tiempo máximo."""
        carpeta = self.carpeta_trabajo / "aceleracion"
        shutil.rmtree(carpeta, ignore_errors=True)
        carpeta.mkdir(parents=True, exist_ok=True)
        salida = carpeta / "resultado.json"
        orden = self._orden or [sys.executable, "-m", "estudio.prueba_aceleracion"]
        entorno = dict(os.environ)
        # Los modelos, en herramientas-ia/modelos; los temporales del acelerador, dentro de trabajo/.
        entorno.update(REMBG_HOME=str(self.carpeta_modelos), U2NET_HOME=str(self.carpeta_modelos), TMPDIR=str(carpeta))
        try:
            with self._candado:
                if self._cancelada:
                    return {"estado": "cancelada"}
                proceso = self._proceso = subprocess.Popen(
                    [*orden, modelo, str(self.carpeta_modelos), str(salida), str(self.tiempo_maximo)],
                    cwd=Path(__file__).resolve().parent.parent, env=entorno,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            try:
                codigo = proceso.wait(timeout=self.tiempo_maximo)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()
                return {"estado": "tiempo"}
            if self._cancelada:
                return {"estado": "cancelada"}
            if codigo != 0:
                return {"estado": "fallo"}
            resultado = json.loads(salida.read_text(encoding="utf-8"))
            return resultado if isinstance(resultado, dict) else {"estado": "fallo"}
        except (OSError, ValueError):
            return {"estado": "fallo"}
        finally:
            with self._candado:
                self._proceso = None
            shutil.rmtree(carpeta, ignore_errors=True)

    def cancelar(self) -> None:
        """Al cerrar la herramienta: corta la prueba si está en marcha, para no dejar ningún proceso suelto."""
        with self._candado:
            self._cancelada = True
            proceso = self._proceso
        if proceso is not None and proceso.poll() is None:
            proceso.kill()
