"""Paso 12: el servidor. Se arranca de verdad en 127.0.0.1 y se le habla por HTTP, con OpenRouter simulado."""

from __future__ import annotations

import io
import json
import socket
import zipfile

import pytest
from PIL import Image

import ayudas
from conftest import MUESTRAS, RAIZ

CABECERAS_JSON = {"Content-Type": "application/json"}


def _subir(servidor, archivos: list[tuple[str, bytes]]):
    return servidor.cliente.post("/api/fotos", files=[("fotos", (nombre, datos, "image/jpeg")) for nombre, datos in archivos])


def _dos_fotos(servidor) -> list[str]:
    respuesta = _subir(servidor, [("bolsa_mesa.jpg", ayudas.foto(1024, 1024)), ("taza_logo.jpg", ayudas.foto(896, 1200))])
    assert respuesta.status_code == 200, respuesta.text
    servidor.esperar("recorte")
    return [foto["id"] for foto in respuesta.json()["fotos"]]


def _crudo(servidor, peticion: bytes) -> bytes:
    """Una petición escrita a mano, para lo que un cliente normal no deja enviar."""
    with socket.create_connection(("127.0.0.1", servidor.puerto), timeout=10) as conexion:
        conexion.sendall(peticion)
        conexion.settimeout(10)
        datos = b""
        try:
            while trozo := conexion.recv(65536):
                datos += trozo
        except TimeoutError:
            pass
    return datos


# --- Estado, cabeceras y lo que no existe -----------------------------------------------------------------------------


def test_el_estado_y_las_opciones(servidor):
    respuesta = servidor.cliente.get("/api/estado")
    assert respuesta.status_code == 200
    estado = respuesta.json()
    assert (estado["herramienta"], estado["version"], estado["fotos"]) == ("estudio-fotos", "1", [])
    assert estado["clave"] == {"guardada": False, "mascara": None}
    assert estado["gasto"]["tope"] == "1,00 $"

    opciones = servidor.cliente.get("/api/opciones").json()
    assert [p["id"] for p in opciones["plataformas"]] == [
        "mercadolibre", "amazon", "shopify", "tiendanube", "instagram", "catalogo-meta", "whatsapp", "google",
    ]
    assert len(opciones["escenas"]) == 5 and len(opciones["modelos_escenas"]) == 4


def test_cada_respuesta_lleva_las_cabeceras_de_seguridad(servidor):
    for ruta in ("/api/estado", "/estilo/estilo.css", "/no-existe", "/api/fotos/nada/vista"):
        cabeceras = servidor.cliente.get(ruta).headers
        csp = cabeceras["content-security-policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "connect-src 'self'" in csp
        assert "http" not in csp and "unsafe" not in csp and "*" not in csp  # nada de internet ni de código suelto
        assert cabeceras["x-content-type-options"] == "nosniff"
        assert cabeceras["x-frame-options"] == "DENY"
        assert cabeceras["referrer-policy"] == "no-referrer"
        assert "access-control-allow-origin" not in cabeceras  # ninguna otra web puede leer las respuestas
    assert servidor.cliente.get("/api/estado").headers["cache-control"] == "no-store"


@pytest.mark.parametrize("ruta", ["/docs", "/redoc", "/openapi.json", "/api/no-existe", "/cualquier/cosa", "/api"])
def test_no_hay_documentacion_automatica_y_lo_que_no_existe_se_dice_en_espanol(servidor, ruta):
    respuesta = servidor.cliente.get(ruta)
    assert respuesta.status_code == 404
    assert respuesta.json() == {"error": "Esa dirección no existe."}


@pytest.mark.parametrize("metodo, ruta", [("POST", "/api/estado"), ("GET", "/api/medidas"), ("PATCH", "/api/ajustes"), ("OPTIONS", "/api/escenas"), ("PUT", "/api/fotos")])
def test_un_metodo_que_no_toca_se_dice_en_espanol(servidor, metodo, ruta):
    respuesta = servidor.cliente.request(metodo, ruta)
    assert respuesta.status_code == 405
    assert respuesta.json() == {"error": "Esa acción no está permitida aquí."}


def test_los_archivos_de_la_pagina_son_locales(servidor):
    css = servidor.cliente.get("/estilo/estilo.css")
    assert css.status_code == 200 and css.headers["content-type"].startswith("text/css")
    logo = servidor.cliente.get("/marca/ismagit_negro.png")
    assert logo.status_code == 200 and logo.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize(
    "ruta",
    ["/estilo/../AGENTS.md", "/estilo/..%2FAGENTS.md", "/estilo/%2e%2e/AGENTS.md", "/marca/../instrucciones.md",
     "/web/../pyproject.toml", "/web/..%2Fpyproject.toml", "/estilo//etc/hosts", "/marca/..%5C..%5CAGENTS.md"],
)
def test_no_se_puede_salir_de_las_carpetas_de_la_pagina(servidor, ruta):
    respuesta = _crudo(servidor, f"GET {ruta} HTTP/1.1\r\nHost: 127.0.0.1:{servidor.puerto}\r\nConnection: close\r\n\r\n".encode())
    assert respuesta.startswith(b"HTTP/1.1 404"), respuesta[:80]
    assert b"herramientas-ia" not in respuesta and b"Reglas fijas" not in respuesta


# --- Solo desde su propia página ------------------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "evil.example:8601", "192.168.1.20:8601", "0.0.0.0:8601", "[::1]:8601", "localhost.evil.example", ""])
def test_un_host_que_no_es_este_computador_se_rechaza(servidor, host):
    for metodo, ruta in (("GET", "/api/estado"), ("GET", "/"), ("POST", "/api/escenas"), ("GET", "/estilo/estilo.css")):
        respuesta = servidor.cliente.request(metodo, ruta, headers={"Host": host})
        assert respuesta.status_code == 400
        assert respuesta.json() == {"error": "Esta herramienta solo se puede usar desde su propia página, en este computador."}


def test_localhost_y_127_0_0_1_valen(servidor):
    for host in (f"127.0.0.1:{servidor.puerto}", f"localhost:{servidor.puerto}", "localhost", "127.0.0.1"):
        assert servidor.cliente.get("/api/estado", headers={"Host": host}).status_code == 200


def test_otra_web_no_puede_usar_la_herramienta(servidor, simulador):
    """Una página de internet abierta en el mismo navegador no puede leer el estado ni gastar."""
    otros = ["https://evil.example", "http://evil.example", "null", f"http://127.0.0.1:{servidor.puerto + 1}",
             f"https://127.0.0.1:{servidor.puerto}", f"http://localhost:{servidor.puerto}", "http://127.0.0.1"]
    cuerpo = json.dumps({"fotos": ["x"], "escena": "cocina", "formato": "1:1", "confirmado": True, "costo_estimado_usd": 0.04})
    for origen in otros:
        cabeceras = {"Origin": origen}
        assert servidor.cliente.get("/api/estado", headers=cabeceras).status_code == 403
        respuesta = servidor.cliente.post("/api/escenas", content=cuerpo, headers={**cabeceras, **CABECERAS_JSON})
        assert respuesta.status_code == 403
        assert respuesta.json() == {"error": "Esta herramienta solo se puede usar desde su propia página, en este computador."}
        assert servidor.cliente.put("/api/ajustes/clave", content='{"clave": "x"}', headers={**cabeceras, **CABECERAS_JSON}).status_code == 403
        assert servidor.cliente.delete("/api/fotos", headers=cabeceras).status_code == 403
    for sitio in ("cross-site", "same-site"):
        assert servidor.cliente.get("/api/estado", headers={"Sec-Fetch-Site": sitio}).status_code == 403
    assert simulador.peticiones == []
    assert not servidor.config.env.exists()


def test_la_propia_pagina_si_puede(servidor):
    propio = {"Origin": servidor.url, "Sec-Fetch-Site": "same-origin"}
    assert servidor.cliente.get("/api/estado", headers=propio).status_code == 200
    assert servidor.cliente.put("/api/ajustes", content='{"negocio": {"nombre": "Café 2600"}}', headers={**propio, **CABECERAS_JSON}).status_code == 200
    por_localhost = {"Host": f"localhost:{servidor.puerto}", "Origin": f"http://localhost:{servidor.puerto}"}
    assert servidor.cliente.get("/api/estado", headers=por_localhost).status_code == 200
    # Abrir la página desde un enlace (por ejemplo, el de la página de inicio) sí se puede.
    assert servidor.cliente.get("/estilo/estilo.css", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


# --- Fotos ----------------------------------------------------------------------------------------------------------


def test_subir_fotos_responde_foto_a_foto(servidor):
    respuesta = _subir(servidor, [
        ("bolsa mesa.jpg", ayudas.foto(1024, 1024)),
        ("notas.jpg", b"esto es un texto, no una foto"),
        ("pequena.png", ayudas.foto(800, 600, "PNG")),
        ("mini.jpg", ayudas.foto(400, 900)),
    ])
    assert respuesta.status_code == 200
    fotos = respuesta.json()["fotos"]
    assert [(f["archivo"], f["aceptada"]) for f in fotos] == [("bolsa_mesa.jpg", True), ("notas.jpg", False), ("pequena.png", True), ("mini.jpg", False)]
    assert fotos[0]["aviso"] is None and "id" in fotos[0]
    assert fotos[1]["error"] == "Este archivo no es una foto JPG, PNG o WEBP."
    assert "1.000" in fotos[2]["aviso"]
    assert fotos[3]["error"] == "La foto mide 400 px de lado corto: se necesitan al menos 500."

    servidor.esperar("recorte")
    estado = servidor.cliente.get("/api/estado").json()
    assert [f["archivo"] for f in estado["fotos"]] == ["bolsa_mesa.jpg", "pequena.png"]
    assert estado["trabajos"]["recorte"]["texto"].startswith("2 de 2 · listo")

    foto = estado["fotos"][0]
    antes = servidor.cliente.get(f"/api/fotos/{foto['id']}/vista")
    despues = servidor.cliente.get(f"/api/fotos/{foto['id']}/recorte")
    assert antes.headers["content-type"] == "image/jpeg" and despues.headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(despues.content)) as recorte:
        assert recorte.mode == "RGBA"  # el después, con transparencia
    png = servidor.cliente.get(foto["recorte"]["url"])
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_veinte_fotos_si_y_veintiuna_no(servidor):
    pequena = ayudas.foto(600, 600)
    respuesta = _subir(servidor, [(f"foto_{n}.jpg", pequena) for n in range(21)])
    assert respuesta.status_code == 400
    assert respuesta.json() == {"error": "Se pueden subir hasta 20 fotos a la vez."}
    assert servidor.cliente.get("/api/estado").json()["fotos"] == []  # no se guardó ninguna

    respuesta = _subir(servidor, [(f"foto_{n}.jpg", pequena) for n in range(20)])
    assert respuesta.status_code == 200
    assert len(respuesta.json()["fotos"]) == 20 and all(f["aceptada"] for f in respuesta.json()["fotos"])
    servidor.esperar("recorte")
    assert servidor.cliente.get("/api/estado").json()["trabajos"]["recorte"]["texto"].startswith("20 de 20 · listo")


def test_cientos_de_archivos_tampoco_rompen_nada(servidor):
    respuesta = _subir(servidor, [(f"f{n}.jpg", b"x") for n in range(150)])
    assert respuesta.status_code == 400 and respuesta.json() == {"error": "Se pueden subir hasta 20 fotos a la vez."}


def test_el_nombre_que_llega_nunca_se_usa_como_ruta(servidor):
    respuesta = _subir(servidor, [("../../../fuera.jpg", ayudas.foto(600, 600)), ("C:\\Users\\alguien\\Desktop\\mi foto.jpg", ayudas.foto(600, 600)), ("..", b"nada")])
    fotos = respuesta.json()["fotos"]
    assert [f["archivo"] for f in fotos[:2]] == ["fuera.jpg", "mi_foto.jpg"]
    assert fotos[2]["aceptada"] is False and "/" not in fotos[2]["archivo"]
    assert "alguien" not in respuesta.text and ".." not in respuesta.text
    servidor.esperar("recorte")
    datos = servidor.config.datos
    assert not (datos.parent / "fuera.jpg").exists() and not list(datos.parent.glob("**/fuera.jpg"))
    assert "alguien" not in servidor.cliente.get("/api/estado").text


def test_subidas_que_no_son_un_formulario_de_fotos(servidor):
    sin_fotos = servidor.cliente.post("/api/fotos", files=[("otro", ("a.jpg", b"x", "image/jpeg"))])
    assert (sin_fotos.status_code, sin_fotos.json()) == (400, {"error": "No llegó ninguna foto."})
    como_json = servidor.cliente.post("/api/fotos", content="{}", headers=CABECERAS_JSON)
    assert (como_json.status_code, como_json.json()) == (415, {"error": "Las fotos deben enviarse desde la página."})


def test_una_subida_que_pesa_demasiado_se_rechaza_antes_de_recibirla(servidor):
    cabeza = f"POST /api/fotos HTTP/1.1\r\nHost: 127.0.0.1:{servidor.puerto}\r\nContent-Type: multipart/form-data; boundary=x\r\nConnection: close\r\n"
    enorme = _crudo(servidor, (cabeza + "Content-Length: 99999999999\r\n\r\n").encode())
    assert enorme.startswith(b"HTTP/1.1 413")
    assert "sube menos fotos a la vez".encode() in enorme
    sin_peso = _crudo(servidor, (cabeza + "Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n").encode())
    assert sin_peso.startswith(b"HTTP/1.1 411")
    # Con los dos a la vez manda «por trozos» y el peso declarado sería mentira: tampoco se recibe (fotos y logo).
    # La respuesta llega con solo las cabeceras: el servidor no espera a recibir ni un trozo.
    for ruta in ("/api/fotos", "/api/ajustes/logo"):
        trampa = _crudo(servidor, (
            cabeza.replace("/api/fotos", ruta) + "Content-Length: 10\r\nTransfer-Encoding: chunked\r\n\r\n"
        ).encode())
        assert trampa.startswith(b"HTTP/1.1 411"), ruta
        assert "La subida no dice cuánto pesa".encode() in trampa
    assert servidor.cliente.get("/api/estado").json()["fotos"] == []
    assert servidor.cliente.get("/api/logo").status_code == 404
    assert list(servidor.config.trabajo.glob("subidas/*")) == []  # sin restos de ninguna subida


def test_quitar_una_foto_y_empezar_de_nuevo(servidor):
    uno, dos = _dos_fotos(servidor)
    assert servidor.cliente.delete(f"/api/fotos/{uno}").json() == {"ok": True}
    repetido = servidor.cliente.delete(f"/api/fotos/{uno}")
    assert (repetido.status_code, repetido.json()) == (404, {"error": "Esa foto ya no está en la lista."})
    assert [f["id"] for f in servidor.cliente.get("/api/estado").json()["fotos"]] == [dos]
    assert servidor.cliente.get(f"/api/fotos/{uno}/vista").status_code == 404

    recortes = sorted(p.name for p in (servidor.estudio.carpeta_salidas / "recortes").iterdir())
    assert servidor.cliente.delete("/api/fotos").json() == {"ok": True}
    assert servidor.cliente.get("/api/estado").json()["fotos"] == []
    assert sorted(p.name for p in servidor.config.salidas.rglob("*_recorte.png")) == recortes  # salidas/ no se borra


def test_reintentar_la_descarga_del_modelo(servidor):
    assert servidor.cliente.post("/api/modelo/reintentar").json() == {"ok": True}


# --- Medidas, archivos y descarga -----------------------------------------------------------------------------------


def test_medidas_archivos_y_zip(servidor):
    ids = _dos_fotos(servidor)
    respuesta = servidor.cliente.post("/api/medidas", json={"fotos": ids, "plataformas": ["mercadolibre", "amazon", "instagram"]})
    assert (respuesta.status_code, respuesta.json()) == (200, {"archivos": 6})
    servidor.esperar("medidas")

    fotos = servidor.cliente.get("/api/estado").json()["fotos"]
    salidas = fotos[0]["salidas"]
    assert [s["plataforma"] for s in salidas] == ["mercadolibre", "amazon", "instagram"]
    archivo = servidor.cliente.get(salidas[0]["url"])
    assert archivo.status_code == 200 and archivo.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(archivo.content)) as imagen:
        assert imagen.size == (1200, 1200) and imagen.getpixel((2, 2)) == (255, 255, 255)

    todo = servidor.cliente.get("/api/descargar")
    assert todo.status_code == 200 and todo.headers["content-type"] == "application/zip"
    assert "attachment" in todo.headers["content-disposition"] and ".zip" in todo.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(todo.content)) as archivo_zip:
        nombres = archivo_zip.namelist()
    assert "resumen.csv" in nombres and len([n for n in nombres if n.endswith(".jpg")]) == 6
    assert len([n for n in nombres if n.startswith("recortes/")]) == 2

    una = servidor.cliente.get("/api/descargar", params={"plataforma": "amazon"})
    with zipfile.ZipFile(io.BytesIO(una.content)) as archivo_zip:
        assert sorted(n.split("/")[0] for n in archivo_zip.namelist()) == ["amazon", "amazon", "resumen.csv"]


def test_solo_se_sirven_los_archivos_que_la_herramienta_creo(servidor):
    uno, _ = _dos_fotos(servidor)
    base = f"/api/archivos/{uno}"
    for nombre in ("no-existe.jpg", "original", "vista.jpg", "..%2F..%2Fajustes.json", "%2e%2e%2f%2e%2e%2fpyproject.toml",
                   "..%5C..%5Cajustes.json", "bolsa_mesa_recorte.png%00.jpg"):
        respuesta = _crudo(servidor, f"GET {base}/{nombre} HTTP/1.1\r\nHost: 127.0.0.1:{servidor.puerto}\r\nConnection: close\r\n\r\n".encode())
        assert respuesta.startswith(b"HTTP/1.1 404"), (nombre, respuesta[:60])
    assert servidor.cliente.get("/api/archivos/otra-foto/bolsa_mesa_recorte.png").status_code == 404
    assert servidor.cliente.get(f"{base}/bolsa_mesa_recorte.png").status_code == 200

    for filtro in ("../../x", "no-existe", "..", "/etc"):
        respuesta = servidor.cliente.get("/api/descargar", params={"plataforma": filtro})
        assert (respuesta.status_code, respuesta.json()) == (404, {"error": "Esa plataforma no existe."})
    sin_medidas = servidor.cliente.get("/api/descargar", params={"plataforma": "amazon"})
    assert (sin_medidas.status_code, sin_medidas.json()) == (409, {"error": "Todavía no hay archivos para descargar."})


def test_medidas_sin_fotos_o_sin_plataformas(servidor):
    ids = _dos_fotos(servidor)
    sin_plataformas = servidor.cliente.post("/api/medidas", json={"fotos": ids, "plataformas": []})
    assert (sin_plataformas.status_code, sin_plataformas.json()) == (400, {"error": "Elige al menos una plataforma."})
    sin_fotos = servidor.cliente.post("/api/medidas", json={"fotos": [], "plataformas": ["amazon"]})
    assert (sin_fotos.status_code, sin_fotos.json()) == (400, {"error": "Elige al menos una foto ya recortada."})


@pytest.mark.parametrize(
    "cuerpo",
    ["esto no es json", "[1, 2, 3]", '"texto"', "null", "{}", '{"fotos": "todas", "plataformas": ["amazon"]}',
     '{"fotos": [1, 2], "plataformas": ["amazon"]}', '{"fotos": [{"id": "x"}], "plataformas": ["amazon"]}', "\xff\xfe"],
)
def test_datos_mal_formados_dan_un_mensaje_fijo_que_no_repite_lo_enviado(servidor, cuerpo):
    for metodo, ruta in (("POST", "/api/medidas"), ("POST", "/api/escenas/estimar"), ("POST", "/api/escenas")):
        respuesta = servidor.cliente.request(metodo, ruta, content=cuerpo.encode("latin-1"), headers=CABECERAS_JSON)
        assert respuesta.status_code == 422
        assert respuesta.json() == {"error": "Los datos enviados no tienen la forma esperada."}


def test_los_datos_deben_ser_json_y_de_tamano_razonable(servidor):
    for tipo in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x", ""):
        respuesta = servidor.cliente.post("/api/medidas", content='{"fotos": [], "plataformas": []}', headers={"Content-Type": tipo})
        assert (respuesta.status_code, respuesta.json()) == (415, {"error": "Los datos deben enviarse como JSON."})
    enorme = json.dumps({"propia": "x" * 100_000})
    respuesta = servidor.cliente.put("/api/ajustes", content=enorme, headers=CABECERAS_JSON)
    assert (respuesta.status_code, respuesta.json()) == (413, {"error": "Los datos enviados son demasiado grandes."})


# --- Ajustes y clave ------------------------------------------------------------------------------------------------


def test_ajustes_del_negocio(servidor):
    cambios = {"negocio": {"nombre": "Café 2600", "color_principal": "#1f3b2d", "color_acento": "#C8A04B"},
               "calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5}
    assert servidor.cliente.put("/api/ajustes", json=cambios).json() == {"ok": True}
    estado = servidor.cliente.get("/api/estado").json()
    assert (estado["negocio"]["nombre"], estado["negocio"]["color_principal"]) == ("Café 2600", "#1F3B2D")
    assert estado["ajustes"] == {"calidad_recorte": "rapida", "modelo_escenas": "google/gemini-3-pro-image", "tope_sesion_usd": 2.5, "tope_texto": "2,50 $"}
    guardado = json.loads(servidor.config.ajustes.read_text(encoding="utf-8"))
    assert guardado["negocio"]["nombre"] == "Café 2600" and "clave" not in json.dumps(guardado).lower()

    mal = servidor.cliente.put("/api/ajustes", json={"negocio": {"color_principal": "rojo; background:url(http://x)"}})
    assert (mal.status_code, mal.json()) == (400, {"error": "El color debe tener la forma #RRGGBB, por ejemplo #1F3B2D."})
    otro = servidor.cliente.put("/api/ajustes", json={"modelo_escenas": "otro/modelo"})
    assert (otro.status_code, otro.json()) == (400, {"error": "Ese modelo de escenas no está en la lista."})


@pytest.mark.parametrize("raro", [[], ["1:1"], {}, {"a": 1}])
def test_una_lista_donde_va_un_texto_se_rechaza_con_su_mensaje_y_no_con_un_fallo_interno(servidor, raro):
    """Una lista o un objeto donde va un texto o un número: un 400 con su mensaje, nunca un 500."""
    def rechazada(respuesta, donde) -> None:
        assert respuesta.status_code in (400, 422) and respuesta.json()["error"], (donde, respuesta.status_code, respuesta.text)
        assert respuesta.json()["error"] != "Algo falló dentro de la herramienta. Inténtalo otra vez.", donde

    for campo in ("calidad_recorte", "modelo_escenas", "tope_sesion_usd"):
        rechazada(servidor.cliente.put("/api/ajustes", json={campo: raro}), campo)
    for campo in ("nombre", "color_principal", "color_acento"):
        rechazada(servidor.cliente.put("/api/ajustes", json={"negocio": {campo: raro}}), campo)
    rechazada(servidor.cliente.put("/api/ajustes", json={"negocio": [raro]}), "negocio")
    rechazada(servidor.cliente.put("/api/ajustes/clave", json={"clave": raro}), "clave")

    (foto_id,) = [f["id"] for f in _subir(servidor, [("bolsa.jpg", ayudas.foto(1024, 1024))]).json()["fotos"]]
    servidor.esperar("recorte")
    bien = {"fotos": [foto_id], "escena": "mesa-madera", "formato": "1:1", "confirmado": True, "costo_estimado_usd": 0.04}
    for ruta in ("/api/escenas/estimar", "/api/escenas"):
        for campo in ("escena", "formato"):
            rechazada(servidor.cliente.post(ruta, json={**bien, campo: raro}), (ruta, campo))
        rechazada(servidor.cliente.post(ruta, json={**bien, "escena": "propia", "propia": raro}), (ruta, "propia"))
    rechazada(servidor.cliente.post("/api/medidas", json={"fotos": [foto_id], "plataformas": {"a": raro}}), "plataformas")
    rechazada(servidor.cliente.post("/api/medidas", json={"fotos": [raro], "plataformas": ["amazon"]}), "fotos")
    assert servidor.cliente.get("/api/estado").status_code == 200  # y la herramienta sigue en pie


def test_el_logo_del_negocio(servidor):
    assert servidor.cliente.get("/api/logo").status_code == 404
    logo = (RAIZ / "marca" / "cafe2600_logo.png").read_bytes()
    assert servidor.cliente.post("/api/ajustes/logo", files={"logo": ("logo.png", logo, "image/png")}).json() == {"ok": True}
    servido = servidor.cliente.get("/api/logo")
    assert servido.status_code == 200 and servido.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(servido.content)) as imagen:
        assert imagen.format == "PNG" and max(imagen.size) <= 600
    assert servidor.cliente.get("/api/estado").json()["negocio"]["logo"].startswith("/api/logo?v=")
    assert list(servidor.config.trabajo.glob("subidas/*")) == []  # sin restos de la subida

    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    mal = servidor.cliente.post("/api/ajustes/logo", files={"logo": ("logo.svg", svg, "image/svg+xml")})
    assert (mal.status_code, mal.json()) == (400, {"error": "El logo debe ser una imagen JPG, PNG o WEBP."})

    assert servidor.cliente.delete("/api/ajustes/logo").json() == {"ok": True}
    assert servidor.cliente.get("/api/logo").status_code == 404


def test_la_clave_se_guarda_y_solo_se_ve_enmascarada(servidor, clave_falsa):
    respuesta = servidor.cliente.put("/api/ajustes/clave", json={"clave": clave_falsa})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"clave": {"guardada": True, "mascara": "••••" + clave_falsa[-4:]}}
    assert clave_falsa not in respuesta.text
    estado = servidor.cliente.get("/api/estado")
    assert estado.json()["clave"]["mascara"] == "••••" + clave_falsa[-4:] and clave_falsa not in estado.text
    assert servidor.config.env.read_text(encoding="utf-8") == f"OPENROUTER_API_KEY={clave_falsa}\n"

    probar = servidor.cliente.post("/api/ajustes/clave/probar")
    assert (probar.status_code, probar.json()) == (200, {"mensaje": "Conexión correcta · límite 2,00 $ · usado 0,12 $"})

    borrar = servidor.cliente.delete("/api/ajustes/clave")
    assert borrar.json() == {"clave": {"guardada": False, "mascara": None}}
    assert not servidor.config.env.exists()
    sin_clave = servidor.cliente.post("/api/ajustes/clave/probar")
    assert (sin_clave.status_code, sin_clave.json()) == (409, {"error": "Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes."})


@pytest.mark.parametrize("cuerpo", [{"clave": "una clave con espacios 123456"}, {"clave": ""}, {"clave": None}, {"clave": 12345678}, {}, {"otra": "cosa-12345678"}])
def test_una_clave_que_no_vale_no_se_guarda_ni_se_repite(servidor, cuerpo):
    respuesta = servidor.cliente.put("/api/ajustes/clave", json=cuerpo)
    assert (respuesta.status_code, respuesta.json()) == (400, {"error": "La clave no parece válida: cópiala entera, sin espacios."})
    assert not servidor.config.env.exists()


def test_probar_una_clave_que_openrouter_no_acepta(servidor):
    servidor.cliente.put("/api/ajustes/clave", json={"clave": "sk-or-v1-esta-no-es-la-clave-buena"})
    respuesta = servidor.cliente.post("/api/ajustes/clave/probar")
    assert (respuesta.status_code, respuesta.json()) == (409, {"error": "OpenRouter no acepta esta clave. Revísala en Ajustes."})
    assert "esta-no-es" not in respuesta.text


# --- Escenas ----------------------------------------------------------------------------------------------------------


def test_escenas_el_costo_se_ve_antes_y_solo_se_gasta_al_confirmar(servidor, simulador, clave_falsa):
    ids = _dos_fotos(servidor)
    servidor.cliente.put("/api/ajustes/clave", json={"clave": clave_falsa})
    pedido = {"fotos": ids, "escena": "mesa-madera", "formato": "1:1"}

    estimacion = servidor.cliente.post("/api/escenas/estimar", json=pedido)
    assert estimacion.status_code == 200
    assert estimacion.json()["texto"] == "2 escenas · costo estimado 0,08 $ · ¿Generar?"
    assert simulador.peticiones == []  # estimar no llama a nadie

    sin_confirmar = servidor.cliente.post("/api/escenas", json={**pedido, "costo_estimado_usd": 0.08})
    assert (sin_confirmar.status_code, sin_confirmar.json()) == (400, {"error": "Antes de gastar hay que ver el costo estimado y confirmarlo."})
    for confirmado in ("true", 1, "si"):
        assert servidor.cliente.post("/api/escenas", json={**pedido, "confirmado": confirmado, "costo_estimado_usd": 0.08}).status_code == 400
    otro_costo = servidor.cliente.post("/api/escenas", json={**pedido, "confirmado": True, "costo_estimado_usd": 0.01})
    assert (otro_costo.status_code, otro_costo.json()) == (409, {"error": "El costo estimado ahora es 0,08 $. Míralo y confírmalo de nuevo."})
    assert simulador.peticiones == []

    confirmada = servidor.cliente.post("/api/escenas", json={**pedido, "confirmado": True, "costo_estimado_usd": estimacion.json()["costo_estimado_usd"]})
    assert (confirmada.status_code, confirmada.json()) == (200, {"imagenes": 2, "costo_estimado": "0,08 $"})
    servidor.esperar("escenas")

    estado = servidor.cliente.get("/api/estado").json()
    trabajo = estado["trabajos"]["escenas"]
    assert (trabajo["hechas"], trabajo["costo_estimado"], trabajo["costo_real"]) == (2, "0,08 $", "0,076 $")
    assert estado["gasto"]["sesion"] == "0,076 $"
    escena = estado["fotos"][0]["escenas"][0]
    assert escena["marca"] == "Para redes y fotos secundarias"
    archivo = servidor.cliente.get(escena["url"])
    assert archivo.status_code == 200 and b"trainedAlgorithmicMedia" in archivo.content
    assert len(simulador.imagenes_pedidas()) == 2 and simulador.violaciones == []


def test_escenas_con_el_tope_superado_no_llaman_a_openrouter(servidor, simulador, clave_falsa):
    ids = _dos_fotos(servidor)
    servidor.cliente.put("/api/ajustes/clave", json={"clave": clave_falsa})
    servidor.cliente.put("/api/ajustes", json={"tope_sesion_usd": 0.05})
    pedido = {"fotos": ids, "escena": "cocina", "formato": "4:5"}
    mensaje = "Esto costaría 0,08 $ y en esta sesión te quedan 0,05 $. Sube el tope en Ajustes o genera menos escenas."
    estimacion = servidor.cliente.post("/api/escenas/estimar", json=pedido).json()
    assert (estimacion["se_puede"], estimacion["mensaje"]) == (False, mensaje)
    respuesta = servidor.cliente.post("/api/escenas", json={**pedido, "confirmado": True, "costo_estimado_usd": 0.08})
    assert (respuesta.status_code, respuesta.json()) == (409, {"error": mensaje})
    assert simulador.peticiones == []


def test_escenas_sin_clave(servidor, simulador):
    ids = _dos_fotos(servidor)
    respuesta = servidor.cliente.post("/api/escenas", json={"fotos": ids, "escena": "cocina", "formato": "1:1", "confirmado": True, "costo_estimado_usd": 0.08})
    assert (respuesta.status_code, respuesta.json()) == (400, {"error": "Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes."})
    assert simulador.peticiones == []


# --- Si algo falla por dentro -----------------------------------------------------------------------------------------


def test_un_error_interno_no_cuenta_nada_del_computador(servidor, monkeypatch, clave_falsa):
    def roto():
        raise RuntimeError(f"fallo en /Users/alguien/secreto con {clave_falsa}")

    monkeypatch.setattr(servidor.estudio, "opciones", roto)
    respuesta = servidor.cliente.get("/api/opciones")
    assert respuesta.status_code == 500
    assert respuesta.json() == {"error": "Algo falló dentro de la herramienta. Inténtalo otra vez."}
    assert "alguien" not in respuesta.text and "Traceback" not in respuesta.text and clave_falsa not in respuesta.text
    assert servidor.cliente.get("/api/estado").status_code == 200  # y sigue funcionando


def test_las_muestras_de_cafe_2600_se_pueden_subir(servidor):
    """Las 5 fotos de `muestras/` pasan por el servidor (con el recorte simulado)."""
    archivos = [(ruta.name, ruta.read_bytes()) for ruta in sorted(MUESTRAS.glob("*.jpg"))]
    assert len(archivos) == 5
    fotos = _subir(servidor, archivos).json()["fotos"]
    assert all(f["aceptada"] for f in fotos)
    assert sum(1 for f in fotos if f["aviso"]) == 2  # las dos de 896 px llevan el aviso de menos de 1.000 px
    servidor.esperar("recorte")
    assert servidor.cliente.get("/api/estado").json()["trabajos"]["recorte"]["texto"].startswith("5 de 5 · listo")
