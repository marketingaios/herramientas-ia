"""Paso 8 (y paso 26, versión 1.1): los ajustes en el `ajustes.json` de la carpeta temporal.

Son tres: la calidad del recorte, el modelo de las escenas y el tope de gasto. Desde la versión 1.1 no hay marca del
negocio: ni nombre, ni colores, ni logo.
"""

from __future__ import annotations

import json

import pytest

import ayudas
from conftest import CARPETA
from estudio import ajustes as los_ajustes
from estudio import costos
from estudio.estudio import ErrorEstudio, Estudio

LOS_TRES = {"calidad_recorte", "modelo_escenas", "tope_sesion_usd"}
# Lo que enviaba la página de la versión 1 (o cualquiera que lo imite): ya no significa nada.
MARCA_ANTIGUA = {"nombre": "Mi tienda", "color_principal": "#123456", "color_acento": "#ABCDEF"}


@pytest.fixture
def estudio(config):
    estudio = Estudio(config)
    yield estudio
    estudio.cerrar()


# --- Valores de fábrica y tabla de modelos --------------------------------------------------------------------------


def test_los_modelos_de_escenas_son_los_de_la_ficha():
    assert [(m["id"], m["nombre"], m["costo_partida_usd"]) for m in costos.MODELOS_ESCENAS] == [
        ("google/gemini-nano-banana-2.1", "Nano Banana 2.1", 0.04),
        ("google/gemini-3.1-flash-lite-image", "Nano Banana 2 Lite", 0.04),
        ("google/gemini-3.1-flash-image", "Nano Banana 2", 0.07),
        ("google/gemini-3-pro-image", "Nano Banana Pro", 0.14),
    ]
    assert [m["id"] for m in costos.MODELOS_ESCENAS if m["recomendado"]] == ["google/gemini-nano-banana-2.1"]
    assert costos.modelos_publicos()[0] == {
        "id": "google/gemini-nano-banana-2.1", "nombre": "Nano Banana 2.1 (recomendado)", "costo_partida": "0,04 $",
    }
    assert costos.modelos_publicos()[3]["costo_partida"] == "0,14 $"


def test_de_fabrica_calidad_automatica_modelo_recomendado_y_tope_de_un_dolar(estudio, config):
    assert not config.ajustes.exists()
    assert set(los_ajustes.POR_DEFECTO) == LOS_TRES and set(los_ajustes.CAMPOS) == LOS_TRES
    estado = estudio.publico()
    assert estado["ajustes"] == {
        "calidad_recorte": "automatica",
        "modelo_escenas": "google/gemini-nano-banana-2.1",
        "tope_sesion_usd": 1.0,
        "tope_texto": "1,00 $",
    }
    assert "negocio" not in estado and set(estudio.ajustes) == LOS_TRES


# --- Guardar ----------------------------------------------------------------------------------------------------------


def test_los_ajustes_se_guardan_en_ajustes_json_y_se_recuperan(estudio, config):
    estudio.cambiar_ajustes({"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5})
    guardado = json.loads(config.ajustes.read_text(encoding="utf-8"))
    assert guardado == {"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5}
    assert "clave" not in config.ajustes.read_text(encoding="utf-8").lower()

    otro = Estudio(config)  # como si se reiniciara la herramienta
    assert otro.publico()["ajustes"]["tope_texto"] == "2,50 $"
    assert otro.publico()["ajustes"]["modelo_escenas"] == "google/gemini-3-pro-image"
    assert otro.publico()["modelo"]["etiqueta"] == "Modo rápido"


def test_se_puede_cambiar_un_solo_ajuste(estudio):
    estudio.cambiar_ajustes({"tope_sesion_usd": 3})
    estudio.cambiar_ajustes({"modelo_escenas": "google/gemini-3.1-flash-image"})
    ajustes = estudio.publico()["ajustes"]
    assert (ajustes["tope_sesion_usd"], ajustes["modelo_escenas"]) == (3.0, "google/gemini-3.1-flash-image")
    assert ajustes["calidad_recorte"] == "automatica"


@pytest.mark.parametrize("marca", [MARCA_ANTIGUA, {"color_principal": "rojo"}, {"nombre": "x" * 5000}, "un texto", ["lista"], 7, None])
def test_la_marca_del_negocio_ya_no_existe_lo_que_llegue_se_ignora_y_no_se_guarda(estudio, config, marca):
    """La página ya no la envía. Si llega (una página antigua abierta, o cualquiera), ni se comprueba ni se guarda."""
    estudio.cambiar_ajustes({"negocio": marca, "logo": "logo.png", "otra_cosa": {"a": 1}, "tope_sesion_usd": 2})
    guardado = json.loads(config.ajustes.read_text(encoding="utf-8"))
    assert guardado == {"calidad_recorte": "automatica", "modelo_escenas": "google/gemini-nano-banana-2.1", "tope_sesion_usd": 2.0}
    estado = estudio.publico()
    assert "negocio" not in estado and set(estudio.ajustes) == LOS_TRES
    for texto in (config.ajustes.read_text(encoding="utf-8"), json.dumps(estado, ensure_ascii=False)):
        assert "Mi tienda" not in texto and "#123456" not in texto and "color_principal" not in texto


def test_el_estudio_ya_no_guarda_ni_sirve_ningun_logo(estudio, config):
    for nombre in ("guardar_logo", "quitar_logo", "_negocio_publico"):
        assert not hasattr(estudio, nombre), nombre
    for nombre in ("guardar_logo", "color_sobre", "LOGO_MAX_MB", "NOMBRE_MAXIMO"):
        assert not hasattr(los_ajustes, nombre), nombre
    assert not hasattr(config, "logo")
    for archivo in ("ajustes.py", "estudio.py", "servidor.py"):
        codigo = (CARPETA / "estudio" / archivo).read_text(encoding="utf-8")
        for resto in ('"negocio"', "color_principal", "color_acento", "/api/logo", "ajustes/logo", "guardar_logo"):
            assert resto not in codigo, f"{archivo}: {resto}"


def test_la_calidad_del_recorte_cambia_el_modelo(estudio):
    estudio.cambiar_ajustes({"calidad_recorte": "maxima"})
    assert estudio.publico()["modelo"]["nombre"] == "birefnet-general"
    estudio.cambiar_ajustes({"calidad_recorte": "rapida"})
    assert (estudio.publico()["modelo"]["nombre"], estudio.publico()["modelo"]["total_mb"]) == ("birefnet-general-lite", 224)


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"calidad_recorte": "turbo"}, "La calidad del recorte debe ser Automática, Máxima o Rápida."),
        ({"calidad_recorte": ["maxima"]}, "La calidad del recorte debe ser Automática, Máxima o Rápida."),
        ({"modelo_escenas": "openai/otro-modelo"}, "Ese modelo de escenas no está en la lista."),
        ({"modelo_escenas": ""}, "Ese modelo de escenas no está en la lista."),
        ({"tope_sesion_usd": -1}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": 5000}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ({"tope_sesion_usd": "mucho"}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": float("nan")}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"tope_sesion_usd": True}, "El tope de gasto debe ser un número, por ejemplo 1."),
        ({"negocio": MARCA_ANTIGUA, "tope_sesion_usd": -1}, "El tope de gasto debe estar entre 0 y 1000 dólares."),
        ("no es un objeto", "Los ajustes no tienen la forma esperada."),
    ],
)
def test_un_ajuste_que_no_vale_se_rechaza_y_no_se_guarda_nada(estudio, config, cambios, mensaje):
    antes = estudio.publico()
    with pytest.raises(ErrorEstudio) as error:
        estudio.cambiar_ajustes(cambios)
    assert str(error.value) == mensaje
    assert not config.ajustes.exists()
    assert estudio.publico()["ajustes"] == antes["ajustes"]


def test_un_ajustes_json_roto_no_impide_arrancar(config):
    config.ajustes.parent.mkdir(parents=True, exist_ok=True)
    config.ajustes.write_text("{ roto", encoding="utf-8")
    assert Estudio(config).publico()["ajustes"]["tope_sesion_usd"] == 1.0

    config.ajustes.write_text(json.dumps({
        "modelo_escenas": "modelo/desconocido", "tope_sesion_usd": 4, "calidad_recorte": "maxima",
    }), encoding="utf-8")
    estado = Estudio(config).publico()
    assert estado["ajustes"]["tope_sesion_usd"] == 4.0 and estado["ajustes"]["calidad_recorte"] == "maxima"
    assert estado["ajustes"]["modelo_escenas"] == "google/gemini-nano-banana-2.1"  # el desconocido vuelve al de fábrica


def test_un_ajustes_json_de_la_version_1_se_lee_sin_su_marca(config):
    """El archivo que dejó la versión 1 trae la marca del negocio: los tres ajustes se respetan y lo demás no se usa."""
    config.ajustes.parent.mkdir(parents=True, exist_ok=True)
    config.ajustes.write_text(json.dumps({
        "negocio": MARCA_ANTIGUA, "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 4,
    }), encoding="utf-8")
    estudio = Estudio(config)
    estado = estudio.publico()
    assert estado["ajustes"] == {
        "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 4.0, "tope_texto": "4,00 $",
    }
    assert "negocio" not in estado and "Mi tienda" not in json.dumps(estado, ensure_ascii=False)
    estudio.cambiar_ajustes({"tope_sesion_usd": 5})  # al guardar, el archivo queda solo con los tres ajustes
    assert json.loads(config.ajustes.read_text(encoding="utf-8")) == {
        "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 5.0,
    }


# --- Lo que dejó la versión 1 (paso 27) -------------------------------------------------------------------------------
# Al arrancar se quita la marca del negocio de `ajustes.json` y se borra el logo reducido. Todo en la carpeta temporal.

AJUSTES_V1 = {
    "negocio": MARCA_ANTIGUA, "calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5,
}
SIN_MARCA = {"calidad_recorte": "maxima", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5}


def _carpeta_de_la_version_1(config) -> dict:
    """Deja la carpeta de datos como la dejó la versión 1 y devuelve lo que NO se debe tocar, con su contenido."""
    config.ajustes.write_text(json.dumps(AJUSTES_V1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config.logo_antiguo.write_bytes(ayudas.foto(600, 200, "PNG"))
    intactos = {
        config.gastos: b'{"ts": "2026-11-13T21:56:33Z", "modelo": "google/gemini-nano-banana-2.1", "imagenes": 1}\n',
        config.medicion: b'{"elegido": "procesador"}\n',
        config.salidas / "2026-11-13_215633" / "recortes" / "producto_recorte.png": ayudas.foto(64, 64, "PNG"),
        config.datos / "logo_negocio_original.png": b"otro archivo de quien usa la herramienta",
    }
    for ruta, datos in intactos.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)
    return intactos


def _foto_de(ruta) -> tuple[bytes, int]:
    return ruta.read_bytes(), ruta.stat().st_mtime_ns


def test_una_carpeta_de_la_version_1_queda_limpia_y_conserva_los_tres_ajustes(config, clave_falsa):
    from estudio import clave as la_clave

    intactos = _carpeta_de_la_version_1(config)
    la_clave.guardar(config.env, clave_falsa)  # la clave (falsa) guardada como la guarda la herramienta
    intactos[config.env] = config.env.read_bytes()
    assert config.logo_antiguo.name == "logo_negocio.png" and config.logo_antiguo.parent == config.datos

    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)

    assert json.loads(config.ajustes.read_text(encoding="utf-8")) == SIN_MARCA  # idénticos, y nada más
    assert "Mi tienda" not in config.ajustes.read_text(encoding="utf-8")
    assert not config.logo_antiguo.exists()
    for ruta, datos in intactos.items():  # lo demás de la carpeta, tal como estaba
        assert ruta.read_bytes() == datos, ruta.name
    assert sorted(p.name for p in config.datos.iterdir() if p.is_file()) == [
        "ajustes.json", "gastos.jsonl", "logo_negocio_original.png", "medicion.json",
    ]  # sin restos temporales

    # Una segunda arrancada no cambia nada: el archivo ya limpio ni se vuelve a escribir.
    antes = _foto_de(config.ajustes)
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)
    assert _foto_de(config.ajustes) == antes and not config.logo_antiguo.exists()

    # Y la herramienta arranca con esos tres ajustes.
    estudio = Estudio(config)
    assert estudio.publico()["ajustes"] == {**SIN_MARCA, "tope_texto": "2,50 $"}
    estudio.cerrar()


def test_los_tres_ajustes_se_conservan_tal_como_estaban_aunque_falte_alguno_o_no_valga(config):
    """La limpieza no arregla ni inventa valores: solo quita lo que sobra."""
    config.ajustes.write_text(json.dumps({"tope_sesion_usd": 7, "negocio": MARCA_ANTIGUA, "modelo_escenas": "modelo/desconocido", "otra": 1}), encoding="utf-8")
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)
    assert json.loads(config.ajustes.read_text(encoding="utf-8")) == {"modelo_escenas": "modelo/desconocido", "tope_sesion_usd": 7}


@pytest.mark.parametrize("contenido", [
    b"{ roto", b"", b"\xff\xfe no es texto", b'["una", "lista"]', b'"un texto"', b"null",
    json.dumps(SIN_MARCA).encode(), b'{"tope_sesion_usd": 3}', b"{}",
])
def test_un_ajustes_json_roto_o_ya_limpio_no_se_toca_y_no_impide_arrancar(config, contenido):
    config.ajustes.write_bytes(contenido)
    config.logo_antiguo.write_bytes(b"un logo")
    antes = _foto_de(config.ajustes)
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)
    assert _foto_de(config.ajustes) == antes  # ni un byte, ni la fecha
    assert not config.logo_antiguo.exists()  # el logo se borra igual
    estudio = Estudio(config)
    assert set(estudio.publico()["ajustes"]) == {"calidad_recorte", "modelo_escenas", "tope_sesion_usd", "tope_texto"}
    estudio.cerrar()


def test_sin_archivos_de_la_version_1_no_pasa_nada_ni_se_crea_nada(config):
    assert not config.ajustes.exists() and not config.logo_antiguo.exists()
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)
    assert not config.ajustes.exists() and not config.logo_antiguo.exists()


def test_si_el_logo_no_se_puede_borrar_o_los_ajustes_no_se_pueden_escribir_arranca_igual(config, monkeypatch):
    _carpeta_de_la_version_1(config)
    config.logo_antiguo.unlink()
    config.logo_antiguo.mkdir()  # algo que no se puede borrar como un archivo
    (config.logo_antiguo / "dentro.txt").write_text("no se toca", encoding="utf-8")

    def sin_permiso(*_argumentos, **_opciones):
        raise PermissionError("no se puede escribir en /una/ruta/privada")

    monkeypatch.setattr(los_ajustes, "guardar", sin_permiso)
    antes = _foto_de(config.ajustes)
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)  # no lanza nada
    assert _foto_de(config.ajustes) == antes
    assert (config.logo_antiguo / "dentro.txt").read_text(encoding="utf-8") == "no se toca"
    monkeypatch.undo()

    estudio = Estudio(config)  # y la herramienta arranca, con sus tres ajustes
    assert estudio.publico()["ajustes"]["tope_sesion_usd"] == 2.5 and "negocio" not in estudio.publico()
    estudio.cerrar()


def test_si_el_logo_es_un_enlace_solo_se_borra_el_enlace(config, tmp_path):
    original = tmp_path / "logo-de-quien-usa-la-herramienta.png"
    original.write_bytes(b"el logo original")
    try:
        config.logo_antiguo.symlink_to(original)
    except OSError:
        pytest.skip("este sistema no deja crear enlaces")
    los_ajustes.limpiar_version_1(config.ajustes, config.logo_antiguo)
    assert not config.logo_antiguo.is_symlink() and original.read_bytes() == b"el logo original"


def test_la_limpieza_se_hace_al_arrancar_el_servidor_y_no_escribe_nada_en_la_consola(config, capfd, caplog):
    import logging

    from estudio.servidor import crear_aplicacion

    intactos = _carpeta_de_la_version_1(config)
    with caplog.at_level(logging.DEBUG):
        aplicacion = crear_aplicacion(config)  # como al arrancar de verdad: sin un estudio ya hecho
    try:
        assert json.loads(config.ajustes.read_text(encoding="utf-8")) == SIN_MARCA
        assert not config.logo_antiguo.exists()
        for ruta, datos in intactos.items():
            assert ruta.read_bytes() == datos, ruta.name
        consola = capfd.readouterr()
        escrito = consola.out + consola.err + caplog.text
        for resto in ("Mi tienda", "#123456", "negocio", "logo", str(config.datos_raiz)):
            assert resto not in escrito, resto
    finally:
        aplicacion.state.estudio.cerrar()


def test_la_limpieza_solo_usa_las_dos_rutas_de_la_configuracion():
    """Ni rutas fijas ni búsquedas por la carpeta: `ajustes.json` y el logo antiguo, y nada más."""
    import inspect

    codigo = inspect.getsource(los_ajustes.limpiar_version_1)
    assert "logo_negocio" not in codigo and "glob" not in codigo and "rmtree" not in codigo and "iterdir" not in codigo
    assert codigo.count(".unlink(") == 1 and "Path(logo_antiguo).unlink(missing_ok=True)" in codigo
    assert "registro" not in codigo.split('"""')[2] and "print(" not in codigo
    estudio = (CARPETA / "estudio" / "estudio.py").read_text(encoding="utf-8")
    assert "los_ajustes.limpiar_version_1(self.config.ajustes, self.config.logo_antiguo)" in estudio
