"""Paso 9: el cliente de OpenRouter, siempre contra el simulador (nunca contra el OpenRouter de verdad)."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from estudio import config as cfg
from estudio import openrouter
from estudio.openrouter import Cliente, ErrorOpenRouter
from simulador import error

MODELO = "google/gemini-nano-banana-2.1"
TEXTO = "Usa exactamente el producto de la imagen, sin cambiar la etiqueta. Escena: mesa de madera clara."


def _referencia() -> bytes:
    """El producto sobre fondo blanco, como lo enviaría la herramienta."""
    imagen = Image.new("RGB", (1024, 1024), (255, 255, 255))
    imagen.paste((150, 70, 40), (300, 200, 724, 824))
    memoria = io.BytesIO()
    imagen.save(memoria, "JPEG", quality=90)
    return memoria.getvalue()


REFERENCIA = _referencia()


class Reloj:
    """En vez de dormir de verdad, apunta cuánto se habría esperado."""

    def __init__(self):
        self.esperas = []

    def __call__(self, segundos):
        self.esperas.append(segundos)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def cliente(simulador, clave_falsa, reloj):
    return Cliente(simulador.url, lambda: clave_falsa, dormir=reloj)


def _falla(cliente: Cliente, **opciones) -> ErrorOpenRouter:
    with pytest.raises(ErrorOpenRouter) as fallo:
        cliente.generar(MODELO, TEXTO, "1:1", REFERENCIA, **opciones)
    return fallo.value


# --- Éxito y forma de la petición -----------------------------------------------------------------------------------


def test_la_direccion_de_verdad_es_la_de_openrouter():
    assert cfg.OPENROUTER_URL == "https://openrouter.ai/api/v1"
    assert cfg.Config().openrouter_url == "https://openrouter.ai/api/v1"


@pytest.mark.parametrize("formato, medida", [("1:1", (1024, 1024)), ("4:5", (928, 1152)), ("16:9", (1344, 768))])
def test_generar_devuelve_la_imagen_y_el_costo_real(cliente, simulador, formato, medida):
    imagen = cliente.generar(MODELO, TEXTO, formato, REFERENCIA)
    assert imagen.costo == 0.038  # usage.cost
    with Image.open(io.BytesIO(imagen.datos)) as abierta:  # data[0].b64_json
        assert abierta.size == medida
    assert simulador.violaciones == []


def test_la_peticion_tiene_exactamente_la_forma_de_la_ficha(cliente, simulador):
    cliente.generar(MODELO, TEXTO, "4:5", REFERENCIA)
    (peticion,) = simulador.peticiones
    assert (peticion["metodo"], peticion["ruta"], peticion["autorizada"]) == ("POST", "/api/v1/images", True)
    cuerpo = peticion["cuerpo"]
    assert set(cuerpo) == {"model", "prompt", "aspect_ratio", "resolution", "input_references"}
    assert (cuerpo["model"], cuerpo["prompt"], cuerpo["aspect_ratio"], cuerpo["resolution"]) == (MODELO, TEXTO, "4:5", "1K")
    (referencia,) = cuerpo["input_references"]
    assert set(referencia) == {"type", "image_url"} and referencia["type"] == "image_url"
    url = referencia["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == REFERENCIA
    assert simulador.violaciones == []


def test_el_simulador_rechaza_lo_que_no_cumple_el_contrato(simulador, clave_falsa):
    """Si el cliente cambiara la forma de la petición, las pruebas lo notarían."""
    import httpx

    cabeceras = {"Authorization": f"Bearer {clave_falsa}"}
    buena = {
        "model": MODELO, "prompt": TEXTO, "aspect_ratio": "1:1", "resolution": "1K",
        "input_references": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(REFERENCIA).decode()}}],
    }
    malas = [
        {**buena, "resolution": "2K"},
        {**buena, "aspect_ratio": "3:2"},
        {**buena, "model": "otro/modelo"},
        {**buena, "size": "1024x1024"},
        {k: v for k, v in buena.items() if k != "input_references"},
        {**buena, "input_references": [{"type": "image_url", "image_url": {"url": "https://example.com/foto.jpg"}}]},
        {**buena, "input_references": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]},
    ]
    with httpx.Client(trust_env=False) as http:
        assert http.post(simulador.url + "/images", json=buena, headers=cabeceras).status_code == 200
        for mala in malas:
            assert http.post(simulador.url + "/images", json=mala, headers=cabeceras).status_code == 400
        assert http.post(simulador.url + "/images", json=buena).status_code == 401
    assert len(simulador.violaciones) == len(malas)


# --- Errores: cada uno con su mensaje ---------------------------------------------------------------------------------


def test_sin_clave_no_se_llama_a_openrouter(simulador, reloj):
    cliente = Cliente(simulador.url, lambda: None, dormir=reloj)
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("sin_clave", "Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes.")
    with pytest.raises(ErrorOpenRouter):
        cliente.probar()
    assert simulador.peticiones == []


def test_clave_no_valida_401(simulador, reloj):
    cliente = Cliente(simulador.url, lambda: "sk-or-v1-esta-clave-no-es-la-buena", dormir=reloj)
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("clave", "OpenRouter no acepta esta clave. Revísala en Ajustes.")
    assert fallo.detiene_el_lote


@pytest.mark.parametrize(
    "respuesta",
    [
        error(402, "Insufficient credits"),
        error(402, "x", limit_source="openrouter_credits"),
        error(402, "x", limit_source="openrouter_key_limit"),
        error(403, "Key limit exceeded", limit_source="openrouter_key_limit"),
        error(403, "x", limit_source="openrouter_credits"),
        error(402, "x", limit_source="openrouter_in_flight_budget", reason="weight_exceeds_budget"),
    ],
)
def test_sin_saldo_o_limite_de_la_clave_agotado_402_y_403(cliente, simulador, reloj, respuesta):
    simulador.guion = [respuesta]
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("saldo", "Se acabó el saldo o el límite de tu clave de OpenRouter.")
    assert fallo.detiene_el_lote
    assert len(simulador.imagenes_pedidas()) == 1 and reloj.esperas == []  # reintentar no sirve: no se reintenta


def test_presupuesto_en_vuelo_402_espera_lo_que_dice_retry_after_y_reintenta(cliente, simulador, reloj):
    simulador.guion = [{**error(402, "x", limit_source="openrouter_in_flight_budget"), "cabeceras": {"Retry-After": "3"}}]
    avisos = []
    imagen = cliente.generar(MODELO, TEXTO, "1:1", REFERENCIA, al_esperar=avisos.append)
    assert imagen.costo == 0.038
    assert reloj.esperas == [3]
    assert avisos == ["OpenRouter pide esperar un momento. Lo intentamos de nuevo en 3 s."]
    assert len(simulador.imagenes_pedidas()) == 2


def test_demasiadas_peticiones_429_espera_y_reintenta(cliente, simulador, reloj):
    simulador.guion = [
        {**error(429, "Rate limited"), "cabeceras": {"Retry-After": "7"}},
        error(429, "Rate limited"),  # sin Retry-After: 5 s
        {**error(429, "Rate limited"), "cabeceras": {"Retry-After": "900"}},  # nunca más de 60 s
    ]
    avisos = []
    imagen = cliente.generar(MODELO, TEXTO, "1:1", REFERENCIA, al_esperar=avisos.append)
    assert imagen.costo == 0.038
    assert reloj.esperas == [7, 5, 60]
    assert avisos[0] == "OpenRouter pide esperar un momento. Lo intentamos de nuevo en 7 s."
    assert len(simulador.imagenes_pedidas()) == 4


def test_si_openrouter_sigue_pidiendo_esperar_se_deja_de_insistir(cliente, simulador, reloj):
    simulador.guion = [{**error(429, "Rate limited"), "cabeceras": {"Retry-After": "2"}}] * 6
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("espera", "OpenRouter sigue pidiendo esperar. Prueba de nuevo en unos minutos.")
    assert fallo.detiene_el_lote
    assert len(simulador.imagenes_pedidas()) == 4 and reloj.esperas == [2, 2, 2]  # la primera y 3 reintentos


@pytest.mark.parametrize(
    "respuesta, tipo, mensaje, detiene",
    [
        (error(502, "Bad gateway"), "generacion", "La escena no se pudo generar y no se cobró. Inténtalo otra vez.", False),
        (error(503, "No provider"), "proveedor", "El modelo no está disponible ahora. Prueba en unos minutos o elige otro en Ajustes.", True),
        (error(400, "Bad request"), "foto", "El modelo no aceptó esta foto. Prueba con otra o con una más pequeña.", False),
        (error(403, "Flagged", reason="content_policy_violation"), "filtro", "El modelo no quiso generar esta escena. Prueba con otra descripción.", False),
        ({"codigo": 403, "cuerpo": {"error": {"code": "content_policy_violation", "message": "x"}}}, "filtro", "El modelo no quiso generar esta escena. Prueba con otra descripción.", False),
        (error(403, "Forbidden"), "otro", "OpenRouter respondió con un error (código 403). Inténtalo otra vez en unos minutos.", True),
        (error(500, "Internal"), "otro", "OpenRouter respondió con un error (código 500). Inténtalo otra vez en unos minutos.", True),
        ({"codigo": 500, "cuerpo": "esto no es json"}, "otro", "OpenRouter respondió con un error (código 500). Inténtalo otra vez en unos minutos.", True),
    ],
)
def test_cada_error_tiene_su_mensaje(cliente, simulador, reloj, respuesta, tipo, mensaje, detiene):
    simulador.guion = [respuesta]
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo), fallo.detiene_el_lote) == (tipo, mensaje, detiene)
    assert len(simulador.imagenes_pedidas()) == 1 and reloj.esperas == []  # ninguno de estos se reintenta solo


@pytest.mark.parametrize(
    "respuesta, tipo",
    [
        # El texto dice una cosa y el código otra: manda el código (y los campos estructurados).
        (error(502, "insufficient credits: key limit exceeded, content_policy_violation, rate limit"), "generacion"),
        (error(402, "content_policy_violation: please retry later, rate limited"), "saldo"),
        (error(400, "openrouter_credits exhausted, 401 unauthorized"), "foto"),
        (error(403, "openrouter_key_limit openrouter_credits"), "otro"),
        (error(503, "invalid api key"), "proveedor"),
    ],
)
def test_un_texto_de_error_enganoso_no_cambia_el_mensaje(cliente, simulador, respuesta, tipo):
    simulador.guion = [respuesta]
    assert _falla(cliente).tipo == tipo


def test_una_respuesta_sin_imagen_es_que_el_modelo_no_quiso(cliente, simulador):
    for cuerpo in ({"data": []}, {"data": [{"b64_json": ""}]}, {"data": [{"b64_json": "bm8gc295IHVuYSBpbWFnZW4="}]}, {}):
        simulador.guion = [{"codigo": 200, "cuerpo": cuerpo}]
        fallo = _falla(cliente)
        assert (fallo.tipo, fallo.detiene_el_lote) == ("filtro", False)


def test_sin_conexion(clave_falsa, reloj):
    cliente = Cliente("http://127.0.0.1:9/api/v1", lambda: clave_falsa, dormir=reloj)  # ahí no escucha nadie
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("conexion", "Sin conexión a internet: el recorte sigue funcionando, las escenas con IA no.")
    assert fallo.detiene_el_lote and not fallo.posible_cobro
    with pytest.raises(ErrorOpenRouter) as fallo_probar:
        cliente.probar()
    assert fallo_probar.value.tipo == "conexion"


def test_si_openrouter_no_responde_a_tiempo_se_avisa_del_posible_cobro(simulador, clave_falsa, reloj):
    simulador.demora = 1.0
    cliente = Cliente(simulador.url, lambda: clave_falsa, dormir=reloj, tiempo_generar=0.2)
    fallo = _falla(cliente)
    assert (fallo.tipo, str(fallo)) == ("tiempo", "OpenRouter no respondió a tiempo. Antes de repetir, mira en openrouter.ai si se cobró.")
    assert fallo.posible_cobro and fallo.detiene_el_lote


def test_ningun_error_lleva_la_clave(simulador, clave_falsa, reloj):
    cliente = Cliente(simulador.url, lambda: clave_falsa, dormir=reloj)
    for respuesta in (error(401, f"Bad key {clave_falsa}"), error(500, clave_falsa), error(402, clave_falsa), error(400, clave_falsa)):
        simulador.guion = [respuesta]
        fallo = _falla(cliente)
        assert clave_falsa not in str(fallo) and clave_falsa not in repr(fallo) and fallo.__cause__ is None
    sin_red = Cliente("http://127.0.0.1:9/api/v1", lambda: clave_falsa, dormir=reloj)
    fallo = _falla(sin_red)
    assert clave_falsa not in repr(fallo) and fallo.__cause__ is None


# --- Probar la clave ----------------------------------------------------------------------------------------------------


def test_probar_dice_el_limite_y_lo_usado(cliente, simulador):
    estado = cliente.probar()
    assert (estado.limite, estado.restante, estado.usado) == (2.0, 1.88, 0.12)
    assert estado.texto() == "Conexión correcta · límite 2,00 $ · usado 0,12 $"
    assert simulador.peticiones == [{"metodo": "GET", "ruta": "/api/v1/key", "autorizada": True}]


def test_probar_con_una_clave_sin_limite(cliente, simulador):
    simulador.llave = {"label": "pruebas", "limit": None, "limit_remaining": None, "usage": 0.12}
    estado = cliente.probar()
    assert estado.limite is None and estado.restante is None
    assert estado.texto() == "Conexión correcta · sin límite · usado 0,12 $"


def test_probar_acepta_la_respuesta_con_data_o_sin_data(cliente, simulador):
    simulador.llave_suelta = True
    assert cliente.probar().texto() == "Conexión correcta · límite 2,00 $ · usado 0,12 $"


def test_probar_con_una_clave_no_valida(simulador, reloj):
    cliente = Cliente(simulador.url, lambda: "sk-or-v1-otra-clave-cualquiera", dormir=reloj)
    with pytest.raises(ErrorOpenRouter) as fallo:
        cliente.probar()
    assert str(fallo.value) == "OpenRouter no acepta esta clave. Revísala en Ajustes."


def test_la_clave_se_lee_en_cada_llamada(simulador, clave_falsa, reloj):
    """Si la clave cambia en el archivo, la siguiente llamada ya usa la nueva: no hay que reiniciar."""
    guardada = {"clave": "sk-or-v1-la-clave-vieja-no-vale"}
    cliente = Cliente(simulador.url, lambda: guardada["clave"], dormir=reloj)
    with pytest.raises(ErrorOpenRouter):
        cliente.probar()
    guardada["clave"] = clave_falsa
    assert cliente.probar().usado == 0.12


def test_los_mensajes_son_los_de_la_ficha():
    assert openrouter.mensaje_espera(12) == "OpenRouter pide esperar un momento. Lo intentamos de nuevo en 12 s."
    assert openrouter.MENSAJES["saldo"] == "Se acabó el saldo o el límite de tu clave de OpenRouter."
    assert openrouter.MENSAJES["conexion"] == "Sin conexión a internet: el recorte sigue funcionando, las escenas con IA no."
