"""Paso 18: la aceleración se mide, no se supone.

La prueba del acelerador corre en otro proceso con un tiempo máximo. Aquí ese proceso se cambia por guiones pequeños
que fallan, tardan demasiado o dicen que el acelerador es más rápido. La medición de verdad en este computador (con
el modelo real y CoreML) va aparte: `pytest -m modelo`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

from conftest import RAIZ, fotos_de_muestra
from estudio import equipo, prueba_aceleracion, recorte
from estudio.config import Config, para_pruebas
from estudio.equipo import PROCESADOR, PROVEEDORES_COREML, Aceleracion
from estudio.estudio import Estudio
from estudio.recorte import RecortadorRembg, RecortadorSimulado
from test_cola import subir

MODELO = "birefnet-general"
CON_COREML = ["CoreMLExecutionProvider", "CPUExecutionProvider"]

# Lo que hace el proceso de mentira. Recibe lo mismo que el de verdad: modelo, carpeta de modelos, resultado y límite.
GUIONES = {
    "falla": "sys.exit(1)",
    "tarda": "time.sleep(60)",
    "rapida": "salida.write_text(json.dumps({'estado': 'bien', 'preparar_s': 12.3, 'segundos': 1.5}))",
    # Para el estudio de las pruebas, cuyo recortador de mentira tarda milésimas: una aceleración aún más rápida.
    "rapidisima": "salida.write_text(json.dumps({'estado': 'bien', 'preparar_s': 0.1, 'segundos': 1e-9}))",
    "lenta": "salida.write_text(json.dumps({'estado': 'bien', 'preparar_s': 30.0, 'segundos': 20.0}))",
    "sin_acelerador": "salida.write_text(json.dumps({'estado': 'sin_acelerador'}))",
    "basura": "salida.write_text('esto no es JSON')",
    "lista": "salida.write_text('[1, 2]')",
    "sin_tiempo": "salida.write_text(json.dumps({'estado': 'bien'}))",
    "tiempo_cero": "salida.write_text(json.dumps({'estado': 'bien', 'segundos': 0}))",
    "tiempo_falso": "salida.write_text(json.dumps({'estado': 'bien', 'segundos': True}))",
    "nada": "pass",
}


def guion(carpeta: Path, nombre: str) -> tuple[list[str], Path]:
    """Un proceso de mentira. Deja anotado en `notas` cada vez que arranca: su PID, sus argumentos y su entorno."""
    notas = carpeta / f"notas-{nombre}.jsonl"
    archivo = carpeta / f"guion_{nombre}.py"
    archivo.write_text(
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "salida = Path(sys.argv[3])\n"
        f"with open({str(notas)!r}, 'a', encoding='utf-8') as notas:\n"
        "    notas.write(json.dumps({'pid': os.getpid(), 'argumentos': sys.argv[1:], 'tmpdir': os.environ.get('TMPDIR'),\n"
        "                            'rembg_home': os.environ.get('REMBG_HOME'), 'u2net_home': os.environ.get('U2NET_HOME'),\n"
        "                            'carpeta_existe': salida.parent.is_dir()}) + '\\n')\n"
        f"{GUIONES[nombre]}\n",
        encoding="utf-8",
    )
    return [sys.executable, str(archivo)], notas


def _notas(notas: Path) -> list[dict]:
    return [json.loads(linea) for linea in notas.read_text(encoding="utf-8").splitlines()] if notas.exists() else []


def _vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.fixture
def crear(tmp_path):
    """Crea una `Aceleracion` de un Mac con CoreML cuyo proceso de prueba es uno de los guiones."""

    def _crear(nombre: str, **opciones) -> tuple[Aceleracion, Path]:
        orden, notas = guion(tmp_path, nombre)
        opciones = {"apple": True, "proveedores": CON_COREML, "orden": orden, **opciones}
        aceleracion = Aceleracion(tmp_path / "medicion.json", tmp_path / "modelos", tmp_path / "trabajo", **opciones)
        return aceleracion, notas

    return _crear


# --- Las tres salidas de la medición ------------------------------------------------------------------------------


def test_si_la_aceleracion_falla_se_sigue_con_el_procesador(crear, tmp_path):
    aceleracion, notas = crear("falla")
    assert aceleracion.hay_que_medir(MODELO)

    medida = aceleracion.medir(MODELO, 7.5)

    assert (medida["elegido"], medida["motivo"], medida["acelerador_s"]) == ("procesador", "fallo", None)
    assert aceleracion.proveedores_para(MODELO) == PROCESADOR
    assert not aceleracion.hay_que_medir(MODELO)  # una sola vez
    assert len(_notas(notas)) == 1
    assert aceleracion.texto(MODELO) == (
        "Medido en este computador: 7,5 s por foto con el procesador. "
        "La aceleración falló al preparar el modelo: se usa el procesador."
    )


def test_si_la_aceleracion_tarda_demasiado_se_corta_y_se_sigue_con_el_procesador(crear):
    aceleracion, notas = crear("tarda", tiempo_maximo=1.0)

    inicio = time.monotonic()
    medida = aceleracion.medir(MODELO, 7.5)
    tardo = time.monotonic() - inicio

    assert (medida["elegido"], medida["motivo"]) == ("procesador", "tiempo")
    assert tardo < 10, f"la prueba no se cortó a tiempo: {tardo:.1f} s"
    assert aceleracion.proveedores_para(MODELO) == PROCESADOR
    assert not aceleracion.hay_que_medir(MODELO)
    assert "tardó más de 2 minutos" in aceleracion.texto(MODELO)
    (nota,) = _notas(notas)
    time.sleep(0.2)
    assert not _vivo(nota["pid"]), "el proceso de la prueba quedó suelto"


def test_si_la_aceleracion_es_mas_rapida_se_elige(crear):
    aceleracion, _ = crear("rapida")

    medida = aceleracion.medir(MODELO, 7.5)

    assert (medida["elegido"], medida["motivo"]) == ("coreml", "mas_rapida")
    assert (medida["procesador_s"], medida["acelerador_s"], medida["preparar_s"]) == (7.5, 1.5, 12.3)
    assert aceleracion.proveedores_para(MODELO) == PROVEEDORES_COREML
    assert not aceleracion.hay_que_medir(MODELO)
    assert aceleracion.texto(MODELO) == (
        "Medido en este computador: 7,5 s por foto con el procesador y 1,5 s con CoreML (MLProgram). "
        "La aceleración es más rápida que el procesador: se usa la aceleración."
    )
    # El otro modelo no se ha medido: sigue con el procesador hasta que se mida.
    assert aceleracion.proveedores_para("birefnet-general-lite") == PROCESADOR
    assert aceleracion.hay_que_medir("birefnet-general-lite")


def test_si_funciona_pero_es_mas_lenta_se_queda_el_procesador(crear):
    aceleracion, _ = crear("lenta")
    medida = aceleracion.medir(MODELO, 7.5)
    assert (medida["elegido"], medida["motivo"], medida["acelerador_s"]) == ("procesador", "mas_lenta", 20.0)
    assert aceleracion.proveedores_para(MODELO) == PROCESADOR
    assert "el procesador es más rápido" in aceleracion.texto(MODELO)


@pytest.mark.parametrize(
    "nombre, motivo",
    [("sin_acelerador", "sin_acelerador"), ("basura", "fallo"), ("lista", "fallo"), ("sin_tiempo", "fallo"),
     ("tiempo_cero", "fallo"), ("tiempo_falso", "fallo"), ("nada", "fallo")],
)
def test_cualquier_resultado_raro_deja_el_procesador(crear, nombre, motivo):
    aceleracion, _ = crear(nombre)
    medida = aceleracion.medir(MODELO, 7.5)
    assert (medida["elegido"], medida["motivo"], medida["acelerador_s"]) == ("procesador", motivo, None)
    assert aceleracion.proveedores_para(MODELO) == PROCESADOR


def test_si_el_proceso_no_se_puede_lanzar_se_sigue_con_el_procesador(tmp_path):
    aceleracion = Aceleracion(
        tmp_path / "medicion.json", tmp_path / "modelos", tmp_path / "trabajo", apple=True, proveedores=CON_COREML,
        orden=[str(tmp_path / "no-existe")],
    )
    assert aceleracion.medir(MODELO, 7.5)["motivo"] == "fallo"


# --- Lo que se guarda y cómo se lanza -----------------------------------------------------------------------------


def test_medicion_json_guarda_lo_medido_sin_rutas_ni_datos_personales(crear, tmp_path):
    aceleracion, _ = crear("rapida")
    aceleracion.medir(MODELO, 7.512)
    crear("falla")[0].medir("birefnet-general-lite", 5.9)  # el otro modelo se añade, no pisa al primero

    texto = (tmp_path / "medicion.json").read_text(encoding="utf-8")
    guardado = json.loads(texto)
    assert set(guardado) == {MODELO, "birefnet-general-lite"}
    for medida in guardado.values():
        assert set(medida) == {"fecha", "acelerador", "procesador_s", "acelerador_s", "preparar_s", "elegido", "motivo"}
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", medida["fecha"])
        assert medida["acelerador"] == "CoreML (MLProgram)"
    assert guardado[MODELO]["procesador_s"] == 7.51 and guardado[MODELO]["elegido"] == "coreml"
    assert guardado["birefnet-general-lite"]["elegido"] == "procesador"
    assert str(tmp_path) not in texto and str(Path.home()) not in texto and "/" not in texto.replace("</", "")
    assert not list(tmp_path.glob("medicion.json.*"))  # no queda el archivo a medio escribir

    # Otra ejecución de la herramienta lee lo guardado y no vuelve a medir.
    otra, notas = crear("nada")
    assert not otra.hay_que_medir(MODELO) and otra.proveedores_para(MODELO) == PROVEEDORES_COREML
    assert _notas(notas) == []


def test_la_prueba_trabaja_en_una_carpeta_de_trabajo_y_la_borra_al_terminar(crear, tmp_path):
    aceleracion, notas = crear("rapida")
    aceleracion.medir(MODELO, 7.5)

    (nota,) = _notas(notas)
    carpeta = tmp_path / "trabajo" / "aceleracion"
    assert nota["argumentos"] == [MODELO, str(tmp_path / "modelos"), str(carpeta / "resultado.json"), "120"]
    assert nota["tmpdir"] == str(carpeta) and nota["carpeta_existe"]  # los temporales del acelerador, en trabajo/
    assert nota["rembg_home"] == nota["u2net_home"] == str(tmp_path / "modelos")  # los modelos, en modelos/
    assert not carpeta.exists()


def test_la_prueba_de_verdad_es_el_modulo_del_estudio_con_dos_minutos_como_maximo(tmp_path, monkeypatch):
    aceleracion = Aceleracion(tmp_path / "medicion.json", tmp_path / "modelos", tmp_path / "trabajo")
    assert aceleracion.tiempo_maximo == equipo.TIEMPO_MAXIMO == 120
    lanzados = []

    class Proceso:
        returncode = 1

        def __init__(self, orden, **opciones):
            lanzados.append((orden, opciones))

        def wait(self, timeout=None):
            lanzados.append(timeout)
            return 1

        def poll(self):
            return 1

    monkeypatch.setattr(equipo.subprocess, "Popen", Proceso)
    assert aceleracion.medir(MODELO, 7.5)["motivo"] == "fallo"
    (orden, opciones), espera = lanzados
    assert orden[:3] == [sys.executable, "-m", "estudio.prueba_aceleracion"] and orden[3] == MODELO
    assert espera == 120
    assert "shell" not in opciones and Path(opciones["cwd"]) == RAIZ / "estudio-fotos"
    # Lo que pide la ficha para un Mac con chip Apple, tal cual.
    assert PROVEEDORES_COREML == [("CoreMLExecutionProvider", {"ModelFormat": "MLProgram"}), "CPUExecutionProvider"]


def test_solo_se_mide_donde_hay_un_acelerador_que_probar(tmp_path):
    def con(**opciones) -> Aceleracion:
        return Aceleracion(tmp_path / "medicion.json", tmp_path / "modelos", tmp_path / "trabajo", **opciones)

    assert con(apple=True, proveedores=CON_COREML).hay_que_medir(MODELO)
    assert not con(apple=True, proveedores=["CPUExecutionProvider"]).hay_que_medir(MODELO)
    assert not con(apple=False, proveedores=CON_COREML).hay_que_medir(MODELO)
    assert not con(apple=False, proveedores=["CUDAExecutionProvider", "CPUExecutionProvider"]).hay_que_medir(MODELO)
    assert con(apple=False, proveedores=CON_COREML).texto(MODELO) is None


def test_un_medicion_json_roto_no_rompe_nada(crear, tmp_path):
    for contenido in ("{esto no es json", "[]", '{"birefnet-general": "coreml"}', '{"birefnet-general": {"elegido": "otro"}}'):
        (tmp_path / "medicion.json").write_text(contenido, encoding="utf-8")
        aceleracion, _ = crear("rapida")
        assert aceleracion.de(MODELO) is None and aceleracion.texto(MODELO) is None
        assert aceleracion.proveedores_para(MODELO) == PROCESADOR and aceleracion.hay_que_medir(MODELO)
    assert aceleracion.medir(MODELO, 7.5)["elegido"] == "coreml"  # y se puede medir y guardar encima


def test_si_se_elige_el_acelerador_sus_temporales_van_a_la_carpeta_de_trabajo(crear, tmp_path, monkeypatch):
    """En el proceso de la herramienta, igual que en el de la prueba: nada se escribe fuera de la carpeta."""
    monkeypatch.setenv("TMPDIR", "/otra/carpeta/temporal")
    aceleracion, _ = crear("rapida")

    assert aceleracion.proveedores_para(MODELO) == PROCESADOR  # sin medir, el procesador
    assert os.environ["TMPDIR"] == "/otra/carpeta/temporal"  # y nada se toca
    aceleracion.medir(MODELO, 7.5)
    assert os.environ["TMPDIR"] == "/otra/carpeta/temporal"  # medir tampoco cambia nada en este proceso

    assert aceleracion.proveedores_para(MODELO) == PROVEEDORES_COREML
    assert os.environ["TMPDIR"] == str(tmp_path / "trabajo" / "acelerador")
    assert (tmp_path / "trabajo" / "acelerador").is_dir()

    # Con el procesador (la medición lo dejó, o el acelerador falló después) no se cambia nada.
    monkeypatch.setenv("TMPDIR", "/otra/carpeta/temporal")
    aceleracion.anotar_fallo(MODELO)
    assert aceleracion.proveedores_para(MODELO) == PROCESADOR
    assert os.environ["TMPDIR"] == "/otra/carpeta/temporal"


def test_si_la_medicion_eligio_coreml_pero_ya_no_hay_coreml_se_usa_el_procesador(crear, tmp_path):
    crear("rapida")[0].medir(MODELO, 7.5)
    sin_coreml = Aceleracion(
        tmp_path / "medicion.json", tmp_path / "modelos", tmp_path / "trabajo", apple=True, proveedores=["CPUExecutionProvider"]
    )
    assert sin_coreml.proveedores_para(MODELO) == PROCESADOR


def test_anotar_fallo_vuelve_al_procesador_y_no_se_intenta_mas(crear):
    aceleracion, notas = crear("rapida")
    aceleracion.medir(MODELO, 7.5)
    assert aceleracion.proveedores_para(MODELO) == PROVEEDORES_COREML

    aceleracion.anotar_fallo(MODELO)

    assert aceleracion.proveedores_para(MODELO) == PROCESADOR and not aceleracion.hay_que_medir(MODELO)
    assert aceleracion.de(MODELO)["motivo"] == "fallo_al_usarla"
    assert "dejó de funcionar al usarla: se usa el procesador" in aceleracion.texto(MODELO)
    assert len(_notas(notas)) == 1


def test_cancelar_corta_la_prueba_y_no_guarda_nada(crear, tmp_path):
    aceleracion, notas = crear("tarda")
    resultado = []
    hilo = threading.Thread(target=lambda: resultado.append(aceleracion.medir(MODELO, 7.5)))
    hilo.start()
    limite = time.monotonic() + 20
    while not _notas(notas) and time.monotonic() < limite:
        time.sleep(0.05)
    (nota,) = _notas(notas)

    aceleracion.cancelar()
    hilo.join(timeout=10)

    assert not hilo.is_alive() and resultado == [None]
    assert not (tmp_path / "medicion.json").exists()  # se medirá la próxima vez
    time.sleep(0.2)
    assert not _vivo(nota["pid"])
    assert aceleracion.medir(MODELO, 7.5) is None and len(_notas(notas)) == 1  # ya cerrada, no lanza nada más


# --- El proceso de la prueba --------------------------------------------------------------------------------------


def test_la_foto_de_prueba_se_dibuja_y_no_usa_ninguna_foto_del_usuario():
    foto = prueba_aceleracion.foto_de_prueba()
    assert foto.mode == "RGB" and foto.size == (1024, 1024)
    assert foto.getpixel((10, 10)) != foto.getpixel((512, 512))  # un «producto» sobre un fondo


@pytest.mark.parametrize(
    "argumentos",
    [[], ["birefnet-general"], ["birefnet-general", "modelos"], ["bria-rmbg", "modelos", "r.json"],
     ["u2net", "modelos", "r.json"], ["birefnet-general", "modelos", "r.json", "mucho"],
     ["birefnet-general", "modelos", "r.json", "120", "sobra"]],
)
def test_el_proceso_de_la_prueba_rechaza_argumentos_raros(argumentos, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(prueba_aceleracion, "crear_sesion", lambda *a, **k: pytest.fail("no debía preparar nada"))
    assert prueba_aceleracion.main(argumentos) == 2
    assert list(tmp_path.iterdir()) == []


def test_el_proceso_de_la_prueba_no_descarga_el_modelo_si_falta(tmp_path, monkeypatch):
    monkeypatch.setattr(prueba_aceleracion, "crear_sesion", lambda *a, **k: pytest.fail("no debía preparar nada"))
    salida = tmp_path / "resultado.json"
    assert prueba_aceleracion.main([MODELO, str(tmp_path / "modelos"), str(salida), "120"]) == 2
    assert not salida.exists() and not (tmp_path / "modelos").exists()


class _SesionDeMentira:
    """Una sesión de rembg de mentira: dice con qué proveedores trabaja y «recorta»."""

    def __init__(self, proveedores, falla_al_recortar=False):
        self.proveedores, self.falla_al_recortar, self.fotos = proveedores, falla_al_recortar, 0
        self.inner_session = self

    def get_providers(self):
        return [p if isinstance(p, str) else p[0] for p in self.proveedores]

    def predict(self, imagen):
        if self.falla_al_recortar:
            raise RuntimeError("el acelerador falló al recortar")
        self.fotos += 1
        return [Image.new("L", imagen.size, 255)]


def test_el_proceso_de_la_prueba_prepara_coreml_recorta_y_escribe_cuanto_tardo(tmp_path, monkeypatch):
    modelos = tmp_path / "modelos"
    archivo = recorte.ruta_modelo(modelos, MODELO)
    archivo.parent.mkdir(parents=True)
    archivo.write_bytes(b"modelo de mentira")
    creadas = []

    def crear_sesion(modelo, carpeta, proveedores):
        creadas.append((modelo, carpeta, proveedores, _SesionDeMentira(proveedores)))
        return creadas[-1][3]

    monkeypatch.setattr(prueba_aceleracion, "crear_sesion", crear_sesion)
    monkeypatch.setattr(prueba_aceleracion.signal, "alarm", lambda segundos: creadas.append(("alarma", segundos)), raising=False)
    salida = tmp_path / "resultado.json"

    assert prueba_aceleracion.main([MODELO, str(modelos), str(salida), "120"]) == 0

    alarma, (modelo, carpeta, proveedores, sesion) = creadas
    assert alarma == ("alarma", 130)  # el proceso se pone su propio límite, por si quien lo lanzó desaparece
    assert (modelo, carpeta, proveedores) == (MODELO, modelos, PROVEEDORES_COREML)  # el modelo, siempre por su nombre
    assert sesion.fotos == 2  # la primera pasada prepara; la segunda es la que se mide
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    assert resultado["estado"] == "bien" and set(resultado) == {"estado", "preparar_s", "segundos"}

    # Si la sesión se crea pero CoreML no queda activo, lo dice y no mide nada.
    monkeypatch.setattr(prueba_aceleracion, "crear_sesion", lambda *a: _SesionDeMentira(PROCESADOR))
    assert prueba_aceleracion.main([MODELO, str(modelos), str(salida), "120"]) == 0
    assert json.loads(salida.read_text(encoding="utf-8")) == {"estado": "sin_acelerador"}


# --- El recortador de verdad, cuando el acelerador falla ----------------------------------------------------------


def test_si_el_acelerador_falla_al_preparar_el_recortador_sigue_con_el_procesador(tmp_path, monkeypatch):
    pedidos = []

    def crear_sesion(modelo, carpeta, proveedores):
        pedidos.append(list(proveedores))
        if proveedores != PROCESADOR:
            raise RuntimeError("CoreML no pudo preparar el modelo")
        return _SesionDeMentira(proveedores)

    monkeypatch.setattr(recorte, "crear_sesion", crear_sesion)
    recortador = RecortadorRembg(MODELO, tmp_path, PROVEEDORES_COREML)
    assert recortador.acelerado() and not recortador.acelerador_fallido

    recortador.preparar()

    assert pedidos == [PROVEEDORES_COREML, PROCESADOR]
    assert recortador.acelerador_fallido and not recortador.acelerado()
    assert recortador.proveedores == PROCESADOR and recortador.pedidos == PROVEEDORES_COREML
    assert recortador.mascara(Image.new("RGB", (64, 64))).size == (64, 64)
    recortador.preparar()
    assert len(pedidos) == 2  # la sesión se crea una sola vez


def test_si_el_acelerador_falla_al_recortar_esa_foto_se_recorta_con_el_procesador(tmp_path, monkeypatch):
    sesiones = []

    def crear_sesion(modelo, carpeta, proveedores):
        sesiones.append(_SesionDeMentira(proveedores, falla_al_recortar=proveedores != PROCESADOR))
        return sesiones[-1]

    monkeypatch.setattr(recorte, "crear_sesion", crear_sesion)
    recortador = RecortadorRembg(MODELO, tmp_path, PROVEEDORES_COREML)
    recortador.preparar()
    assert recortador.acelerado() and recortador.proveedores_activos() == CON_COREML

    assert recortador.mascara(Image.new("RGB", (64, 64))).size == (64, 64)  # el lote no se rompe

    assert recortador.acelerador_fallido and recortador.proveedores == PROCESADOR
    assert [s.proveedores for s in sesiones] == [PROVEEDORES_COREML, PROCESADOR] and sesiones[1].fotos == 1
    recortador.mascara(Image.new("RGB", (64, 64)))
    assert len(sesiones) == 2 and sesiones[1].fotos == 2


def test_con_el_procesador_un_fallo_no_se_esconde(tmp_path, monkeypatch):
    def crear_sesion(modelo, carpeta, proveedores):
        raise MemoryError("no hay memoria")

    monkeypatch.setattr(recorte, "crear_sesion", crear_sesion)
    recortador = RecortadorRembg(MODELO, tmp_path)
    assert not recortador.acelerado()
    with pytest.raises(MemoryError):
        recortador.preparar()
    assert not recortador.acelerador_fallido

    monkeypatch.setattr(recorte, "crear_sesion", lambda *a: _SesionDeMentira(PROCESADOR, falla_al_recortar=True))
    recortador = RecortadorRembg(MODELO, tmp_path)
    with pytest.raises(RuntimeError):
        recortador.mascara(Image.new("RGB", (64, 64)))


# --- En el estudio: después del primer lote, sin parar nada -------------------------------------------------------


class _Fabrica:
    """Crea recortadores de mentira con los proveedores que diga la medición, como hace la fábrica de verdad."""

    def __init__(self, aceleracion: Aceleracion, falla_el_acelerador: bool = False):
        self.aceleracion, self.falla_el_acelerador = aceleracion, falla_el_acelerador
        self.creados: list[list] = []

    def __call__(self, modelo: str):
        proveedores = self.aceleracion.proveedores_para(modelo)
        self.creados.append(proveedores)
        fabrica = self

        class DeMentira(RecortadorSimulado):
            def acelerado(self) -> bool:
                return proveedores != PROCESADOR and not fabrica.falla_el_acelerador

            def preparar(self) -> None:
                super().preparar()
                if proveedores != PROCESADOR and fabrica.falla_el_acelerador:
                    self.acelerador_fallido = True  # como el de verdad: falla y sigue con el procesador

        return DeMentira()


def _estudio(config, tmp_path, nombre: str, **opciones):
    orden, notas = guion(tmp_path, nombre)
    aceleracion = Aceleracion(
        config.medicion, config.modelos, config.trabajo, apple=True, proveedores=CON_COREML, orden=orden, **opciones
    )
    fabrica = _Fabrica(aceleracion)
    return Estudio(config, fabrica, aceleracion=aceleracion), fabrica, notas


def _lote(estudio: Estudio, tmp_path, cuantas: int, prefijo: str) -> list[str]:
    ids = [subir(estudio, tmp_path, f"{prefijo}_{n}.jpg")["id"] for n in range(1, cuantas + 1)]
    assert estudio.esperar("recorte", 30)
    return ids


def test_al_terminar_el_primer_lote_se_mide_una_sola_vez_y_ningun_lote_espera(config, tmp_path):
    estudio, fabrica, notas = _estudio(config, tmp_path, "falla")
    try:
        assert estudio.publico()["modelo"]["medicion"] is None
        _lote(estudio, tmp_path, 3, "primero")
        assert estudio.esperar_medicion(30)

        medida = json.loads(config.medicion.read_text(encoding="utf-8"))[MODELO]
        assert (medida["elegido"], medida["motivo"]) == ("procesador", "fallo")
        assert medida["procesador_s"] is not None and medida["procesador_s"] >= 0
        assert "La aceleración falló al preparar el modelo: se usa el procesador." in estudio.publico()["modelo"]["medicion"]

        _lote(estudio, tmp_path, 2, "segundo")
        assert estudio.esperar_medicion(30)
        estado = estudio.publico()
        assert [foto["estado"] for foto in estado["fotos"]] == ["lista"] * 5
        assert estado["modelo"]["estado"] == "listo"
        assert len(_notas(notas)) == 1  # una sola vez
        assert fabrica.creados == [PROCESADOR]  # y el modelo se preparó una sola vez
    finally:
        estudio.cerrar()


def test_si_la_aceleracion_es_mas_rapida_el_siguiente_lote_la_usa(config, tmp_path):
    estudio, fabrica, notas = _estudio(config, tmp_path, "rapidisima")
    try:
        _lote(estudio, tmp_path, 2, "primero")  # el primer lote no espera: empieza con el procesador
        assert fabrica.creados == [PROCESADOR]
        assert estudio.esperar_medicion(30)
        assert json.loads(config.medicion.read_text(encoding="utf-8"))[MODELO]["elegido"] == "coreml"
        assert "se usa la aceleración" in estudio.publico()["modelo"]["medicion"]

        _lote(estudio, tmp_path, 3, "segundo")  # el modelo se prepara otra vez, ahora con el acelerador
        assert fabrica.creados == [PROCESADOR, PROVEEDORES_COREML]
        _lote(estudio, tmp_path, 2, "tercero")  # y ya no cambia más
        assert fabrica.creados == [PROCESADOR, PROVEEDORES_COREML]
        assert estudio.esperar_medicion(30)

        estado = estudio.publico()
        assert [foto["estado"] for foto in estado["fotos"]] == ["lista"] * 7
        assert len(_notas(notas)) == 1
    finally:
        estudio.cerrar()

    # Al arrancar otra vez, el acelerador se usa desde el primer lote y no se vuelve a medir.
    otro, otra_fabrica, otras_notas = _estudio(config, tmp_path, "falla")
    try:
        _lote(otro, tmp_path, 1, "otro")
        assert otro.esperar_medicion(30)
        assert otra_fabrica.creados == [PROVEEDORES_COREML] and _notas(otras_notas) == []
    finally:
        otro.cerrar()


def test_si_el_acelerador_elegido_falla_al_usarlo_el_lote_sigue_y_queda_anotado(config, tmp_path):
    crear_medida, _ = guion(tmp_path, "rapida")
    Aceleracion(config.medicion, config.modelos, config.trabajo, apple=True, proveedores=CON_COREML, orden=crear_medida).medir(MODELO, 7.5)

    estudio, fabrica, notas = _estudio(config, tmp_path, "falla")
    fabrica.falla_el_acelerador = True
    try:
        _lote(estudio, tmp_path, 3, "lote")
        assert estudio.esperar_medicion(30)
        estado = estudio.publico()
        assert [foto["estado"] for foto in estado["fotos"]] == ["lista"] * 3  # el lote no se rompe
        assert fabrica.creados == [PROVEEDORES_COREML]
        medida = json.loads(config.medicion.read_text(encoding="utf-8"))[MODELO]
        assert (medida["elegido"], medida["motivo"]) == ("procesador", "fallo_al_usarla")
        assert "dejó de funcionar al usarla" in estado["modelo"]["medicion"]
        assert _notas(notas) == []  # no se vuelve a probar
    finally:
        estudio.cerrar()


def test_mientras_se_mide_la_pagina_lo_dice_y_cerrar_corta_la_prueba(config, tmp_path):
    estudio, _, notas = _estudio(config, tmp_path, "tarda")
    try:
        _lote(estudio, tmp_path, 1, "lote")
        limite = time.monotonic() + 20
        while not _notas(notas) and time.monotonic() < limite:
            time.sleep(0.05)
        (nota,) = _notas(notas)
        assert estudio.publico()["modelo"]["medicion"] == equipo.MENSAJE_MIDIENDO
        _lote(estudio, tmp_path, 2, "mientras")  # se puede seguir trabajando mientras se mide
        assert [foto["estado"] for foto in estudio.publico()["fotos"]] == ["lista"] * 3
    finally:
        estudio.cerrar()
    assert estudio.esperar_medicion(10)
    time.sleep(0.2)
    assert not _vivo(nota["pid"]) and not config.medicion.exists()


def test_en_las_pruebas_y_con_el_recortador_simulado_no_se_mide_sola(config, tmp_path):
    assert Config().medir is True and para_pruebas(tmp_path).medir is False and config.medir is False
    estudio = Estudio(config)
    try:
        assert estudio._aceleracion is None
        _lote(estudio, tmp_path, 1, "lote")
        assert estudio.esperar_medicion(5) and not config.medicion.exists()
        assert estudio.publico()["modelo"]["medicion"] is None
    finally:
        estudio.cerrar()
    # Con el modelo de verdad y fuera de las pruebas, sí: la medición va a medicion.json, al lado de los ajustes.
    de_verdad = Config(datos_raiz=tmp_path, datos=tmp_path / "estudio-fotos")
    estudio = Estudio(de_verdad)
    try:
        assert isinstance(estudio._aceleracion, Aceleracion)
        assert estudio._aceleracion.ruta == tmp_path / "estudio-fotos" / "medicion.json"
        assert estudio._aceleracion.carpeta_trabajo == tmp_path / "estudio-fotos" / "trabajo"
    finally:
        estudio.cerrar()


def test_la_pagina_recibe_lo_medido_y_tiene_donde_decirlo(config, tmp_path):
    from conftest import CARPETA, ServidorDePruebas

    estudio, _, _ = _estudio(config, tmp_path, "falla")
    servidor = ServidorDePruebas(config, estudio)
    try:
        assert servidor.cliente.get("/api/estado").json()["modelo"]["medicion"] is None
        _lote(estudio, tmp_path, 1, "lote")
        assert estudio.esperar_medicion(30)
        medicion = servidor.cliente.get("/api/estado").json()["modelo"]["medicion"]
        assert medicion.startswith("Medido en este computador: ")
        assert medicion.endswith("La aceleración falló al preparar el modelo: se usa el procesador.")
        assert str(tmp_path) not in medicion
    finally:
        servidor.parar()
    assert 'id="medicion-modelo"' in (CARPETA / "web" / "index.html").read_text(encoding="utf-8")
    assert '$("medicion-modelo").textContent = modelo.medicion' in (CARPETA / "web" / "app.js").read_text(encoding="utf-8")


# --- La medición de verdad en este computador (aparte: `pytest -m modelo`) ----------------------------------------


@pytest.mark.modelo
def test_medicion_real_despues_del_primer_lote(tmp_path, tmp_path_factory):
    """Con el modelo real: recorta una muestra, mide CoreML en su proceso aparte (2 minutos como máximo) y sigue."""
    aceleracion = Aceleracion(tmp_path / "medicion.json", RAIZ / "modelos", tmp_path / "trabajo")
    if not aceleracion.hay_que_medir(MODELO):
        pytest.skip("este computador no tiene un acelerador que probar")
    config = para_pruebas(tmp_path, recortador="rembg")
    estudio = Estudio(config, aceleracion=aceleracion)
    muestras = fotos_de_muestra()  # hacen falta 3: dos para el primer lote y una para el siguiente
    try:
        estudio.cambiar_calidad("maxima")
        subir(estudio, tmp_path, muestras[0].name, muestras[0].read_bytes())
        subir(estudio, tmp_path, muestras[1].name, muestras[1].read_bytes())
        assert estudio.esperar("recorte", 300)
        inicio = time.monotonic()
        assert estudio.esperar_medicion(equipo.TIEMPO_MAXIMO + 30)
        tardo = time.monotonic() - inicio

        medida = json.loads((tmp_path / "medicion.json").read_text(encoding="utf-8"))[MODELO]
        assert medida["elegido"] in ("procesador", "coreml") and medida["motivo"] in equipo.MOTIVOS
        assert medida["procesador_s"] > 0
        assert not (tmp_path / "trabajo" / "aceleracion").exists()

        # Salga lo que salga, el siguiente lote funciona.
        subir(estudio, tmp_path, muestras[2].name, muestras[2].read_bytes())
        assert estudio.esperar("recorte", 400)
        estado = estudio.publico()
        assert [foto["estado"] for foto in estado["fotos"]] == ["lista"] * 3, [foto["error"] for foto in estado["fotos"]]
        informe = {
            **medida, "modelo": MODELO, "la_prueba_tardo_s": round(tardo, 1), "texto": estado["modelo"]["medicion"],
            "tercera_foto_s": estado["fotos"][2]["segundos"],
        }
        (tmp_path_factory.getbasetemp() / "aceleracion_real.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\nACELERACIÓN REAL:", json.dumps(informe, ensure_ascii=False))
    finally:
        estudio.cerrar()
