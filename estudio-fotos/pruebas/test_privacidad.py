"""Paso 12: después de una sesión completa con una clave falsa, la clave no está en ninguna respuesta, registro,
resultado ni página. Tampoco hay rutas de la carpeta personal.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path

import pytest

import ayudas
from conftest import CARPETA, RAIZ
from estudio import registro as el_registro
from simulador import error

JSON = {"Content-Type": "application/json"}


class Captura(logging.Handler):
    """Guarda todo lo que se registra, tal como saldría por la consola (con las trazas, si las hubiera)."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
        self.lineas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lineas.append(self.format(record))


@pytest.fixture
def registros():
    el_registro.preparar()  # como al arrancar la herramienta de verdad
    captura = Captura()
    nombres = ("", "estudio", "uvicorn", "uvicorn.error", "uvicorn.access")
    for nombre in nombres:
        logging.getLogger(nombre).addHandler(captura)
    yield captura
    for nombre in nombres:
        logging.getLogger(nombre).removeHandler(captura)


def _textos_de(respuesta) -> list[str]:
    """Todo lo que lleva una respuesta: el cuerpo (y lo de dentro, si es un ZIP) y las cabeceras."""
    textos = [respuesta.content.decode("latin-1"), json.dumps(dict(respuesta.headers))]
    if respuesta.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(respuesta.content)) as archivo:
            for nombre in archivo.namelist():
                textos.append(nombre)
                textos.append(archivo.read(nombre).decode("latin-1"))
    return textos


def test_la_clave_no_aparece_en_ningun_sitio(servidor, simulador, clave_falsa, registros, capfd):
    cliente = servidor.cliente
    respuestas = []

    def pedir(metodo: str, ruta: str, **opciones):
        respuesta = cliente.request(metodo, ruta, **opciones)
        respuestas.append((f"{metodo} {ruta.replace(clave_falsa, '<clave>')}", respuesta))
        return respuesta

    # --- Una sesión completa: fotos, medidas, clave, escenas, errores y descargas ---
    subida = pedir("POST", "/api/fotos", files=[("fotos", ("bolsa.jpg", ayudas.foto(1024, 1024), "image/jpeg")),
                                               ("fotos", ("nota.txt", b"no soy una foto", "text/plain"))])
    ids = [foto["id"] for foto in subida.json()["fotos"] if foto["aceptada"]]
    servidor.esperar("recorte")
    pedir("POST", "/api/medidas", json={"fotos": ids, "plataformas": ["mercadolibre", "amazon"]})
    servidor.esperar("medidas")

    guardada = pedir("PUT", "/api/ajustes/clave", json={"clave": clave_falsa})
    assert guardada.json()["clave"]["mascara"] == "••••" + clave_falsa[-4:]
    pedir("PUT", "/api/ajustes", json={"negocio": {"nombre": "Café 2600"}})
    assert pedir("POST", "/api/ajustes/clave/probar").status_code == 200

    # Peticiones mal hechas que llevan la clave donde no toca: ninguna respuesta la repite.
    assert pedir("PUT", "/api/ajustes/clave", content=f'{{"clave": "{clave_falsa}"', headers=JSON).status_code == 422
    assert pedir("PUT", "/api/ajustes/clave", content=f'["{clave_falsa}"]', headers=JSON).status_code == 422
    assert pedir("PUT", "/api/ajustes/clave", content=f"clave={clave_falsa}", headers={"Content-Type": "text/plain"}).status_code == 415
    assert pedir("PUT", "/api/ajustes/clave", json={"clave": f"{clave_falsa} con espacios"}).status_code == 400
    assert pedir("PUT", "/api/ajustes", json={"negocio": {"nombre": clave_falsa}}).status_code == 400
    assert pedir("PUT", "/api/ajustes", json={"negocio": {"color_principal": clave_falsa}}).status_code == 400
    assert pedir("PUT", "/api/ajustes", json={"modelo_escenas": clave_falsa}).status_code == 400
    assert pedir("POST", "/api/medidas", json={"fotos": clave_falsa, "plataformas": [clave_falsa]}).status_code == 422
    assert pedir("POST", "/api/escenas/estimar", json={"fotos": ids, "escena": clave_falsa, "formato": clave_falsa}).status_code == 400
    assert pedir("GET", "/api/descargar", params={"plataforma": clave_falsa}).status_code == 404
    assert pedir("GET", f"/api/archivos/{ids[0]}/{clave_falsa}").status_code == 404
    assert pedir("GET", f"/api/fotos/{clave_falsa}/vista").status_code == 404
    assert pedir("GET", f"/{clave_falsa}").status_code == 404
    assert pedir("GET", f"/estilo/{clave_falsa}.css").status_code == 404
    assert pedir("DELETE", f"/api/fotos/{clave_falsa}").status_code == 404
    assert pedir("POST", "/api/fotos", files=[("fotos", (f"{clave_falsa}.txt", b"x", "text/plain"))]).status_code == 200
    assert pedir("GET", "/api/estado", headers={"Origin": f"http://{clave_falsa}"}).status_code == 403
    assert pedir("GET", "/api/estado", headers={"Host": clave_falsa}).status_code == 400

    # OpenRouter responde con errores que repiten la clave en su texto: el mensaje de la página no la lleva.
    pedido = {"fotos": ids, "escena": "mesa-madera", "formato": "1:1", "confirmado": True}
    for respuesta_simulada in (error(500, f"clave {clave_falsa}"), error(502, clave_falsa), error(401, f"Bad key {clave_falsa}")):
        simulador.guion = [respuesta_simulada]
        estimado = pedir("POST", "/api/escenas/estimar", json=pedido).json()["costo_estimado_usd"]
        assert pedir("POST", "/api/escenas", json={**pedido, "costo_estimado_usd": estimado}).status_code == 200
        servidor.esperar("escenas")
        pedir("GET", "/api/estado")
    estimado = pedir("POST", "/api/escenas/estimar", json=pedido).json()["costo_estimado_usd"]
    assert pedir("POST", "/api/escenas", json={**pedido, "costo_estimado_usd": estimado}).status_code == 200
    servidor.esperar("escenas")

    # Un error interno, con la clave dentro de la excepción.
    original = servidor.estudio.opciones
    servidor.estudio.opciones = lambda: (_ for _ in ()).throw(RuntimeError(f"algo con {clave_falsa} en {Path.home()}"))
    assert pedir("GET", "/api/opciones").status_code == 500
    servidor.estudio.opciones = original

    estado = pedir("GET", "/api/estado").json()
    pedir("GET", "/api/opciones")
    foto = estado["fotos"][0]
    assert len(foto["escenas"]) == 1 and len(foto["salidas"]) == 2
    for archivo in [foto["recorte"], *foto["salidas"], *foto["escenas"]]:
        assert pedir("GET", archivo["url"]).status_code == 200
    pedir("GET", f"/api/fotos/{foto['id']}/vista")
    pedir("GET", f"/api/fotos/{foto['id']}/recorte")
    assert pedir("GET", "/api/descargar").status_code == 200
    assert pedir("GET", "/api/descargar", params={"plataforma": "escenas"}).status_code == 200
    for ruta in ("/", "/estilo/estilo.css", "/estilo/firma.html", "/web/app.js", "/web/app.css", "/marca/ismagit_negro.png"):
        pedir("GET", ruta)
    for metodo, ruta in (("DELETE", "/api/ajustes/clave"), ("PUT", "/api/ajustes/clave")):
        pedir(metodo, ruta, json={"clave": clave_falsa})  # borrar y volver a guardar
    pedir("GET", "/api/estado")

    # --- 1. Ninguna respuesta del servidor contiene la clave, ni rutas de este computador ---
    personales = {str(Path.home()), str(RAIZ), str(CARPETA), str(servidor.config.datos_raiz)}
    assert len(respuestas) >= 50
    for nombre, respuesta in respuestas:
        for texto in _textos_de(respuesta):
            assert clave_falsa not in texto, f"la clave aparece en la respuesta de {nombre}"
            assert clave_falsa[:24] not in texto, f"media clave aparece en la respuesta de {nombre}"
            for ruta in personales:
                assert ruta not in texto, f"una ruta del computador aparece en la respuesta de {nombre}"
    assert any("••••" + clave_falsa[-4:] in respuesta.text for _, respuesta in respuestas)  # solo los 4 últimos

    # --- 2. Ningún registro la contiene (ni rutas de la carpeta personal, ni trazas) ---
    consola = capfd.readouterr()
    registrado = "\n".join(registros.lineas) + consola.out + consola.err
    assert "Error interno en GET /api/opciones (RuntimeError)" in registrado  # el fallo se anota, pero sin detalle
    assert clave_falsa not in registrado and clave_falsa[:24] not in registrado
    assert str(Path.home()) not in registrado and "Traceback" not in registrado

    # --- 3. Ningún resultado ni archivo de datos la contiene: solo está en el archivo de la clave ---
    con_clave = []
    for archivo in servidor.config.datos_raiz.rglob("*"):
        if archivo.is_file() and clave_falsa.encode() in archivo.read_bytes():
            con_clave.append(archivo.relative_to(servidor.config.datos_raiz).as_posix())
    assert con_clave == [".env"]
    gastos = servidor.config.gastos.read_text(encoding="utf-8")
    assert len(gastos.splitlines()) == 1 and "sk-or" not in gastos  # las tres fallidas no se cobraron; la última sí
    assert set(json.loads(gastos.splitlines()[0])) == {"ts", "modelo", "imagenes", "costo_estimado_usd", "costo_usd"}

    # --- 4. La clave solo viajó a OpenRouter (el simulador), en la cabecera de autorización ---
    assert simulador.peticiones and all(p["autorizada"] for p in simulador.peticiones)
    for peticion in simulador.imagenes_pedidas():
        assert clave_falsa not in json.dumps(peticion["cuerpo"])


def test_sin_datos_personales_en_el_estado_ni_en_los_resultados(servidor):
    """Ni nombres, ni correos, ni rutas: lo que ve la página son nombres de archivo y nada más."""
    subida = servidor.cliente.post("/api/fotos", files=[("fotos", ("/Users/maria.perez/Desktop/bolsa.jpg", ayudas.foto(1024, 1024), "image/jpeg"))])
    servidor.esperar("recorte")
    ids = [foto["id"] for foto in subida.json()["fotos"]]
    servidor.cliente.post("/api/medidas", json={"fotos": ids, "plataformas": ["tiendanube"]})
    servidor.esperar("medidas")
    textos = [subida.text, servidor.cliente.get("/api/estado").text, servidor.cliente.get("/api/opciones").text]
    descarga = servidor.cliente.get("/api/descargar")
    with zipfile.ZipFile(io.BytesIO(descarga.content)) as archivo:
        textos += archivo.namelist() + [archivo.read("resumen.csv").decode("utf-8-sig")]
    textos.append(descarga.headers["content-disposition"])
    for texto in textos:
        assert "maria" not in texto and "Desktop" not in texto and "/Users" not in texto
        assert str(Path.home()) not in texto and "@" not in texto


def test_los_jpeg_no_llevan_los_metadatos_de_la_foto_original(servidor):
    """El GPS o el nombre del dueño de la cámara no viajan a los archivos de resultados."""
    from PIL import Image

    imagen = ayudas.imagen_foto(1024, 1024)
    exif = Image.Exif()
    exif[0x013B] = "Maria Perez"  # Artist
    exif[0x010F] = "CamaraSecreta"  # Make
    memoria = io.BytesIO()
    imagen.save(memoria, "JPEG", exif=exif, comment=b"comentario privado")
    subida = servidor.cliente.post("/api/fotos", files=[("fotos", ("bolsa.jpg", memoria.getvalue(), "image/jpeg"))])
    servidor.esperar("recorte")
    foto_id = subida.json()["fotos"][0]["id"]
    servidor.cliente.post("/api/medidas", json={"fotos": [foto_id], "plataformas": ["mercadolibre", "instagram"]})
    servidor.esperar("medidas")
    foto = servidor.cliente.get("/api/estado").json()["fotos"][0]
    rutas = [foto["recorte"]["url"], *(s["url"] for s in foto["salidas"]), f"/api/fotos/{foto_id}/vista", f"/api/fotos/{foto_id}/recorte"]
    for ruta in rutas:
        datos = servidor.cliente.get(ruta).content
        assert b"Maria Perez" not in datos and b"CamaraSecreta" not in datos and b"comentario privado" not in datos, ruta


# --- El filtro de los registros -------------------------------------------------------------------------------------


def test_el_filtro_de_registros_tapa_claves_y_la_carpeta_personal(clave_falsa):
    assert el_registro.limpiar(f"clave {clave_falsa} fin") == "clave •••• fin"
    assert el_registro.limpiar(f"Authorization: Bearer {clave_falsa}") == "Authorization: Bearer ••••"
    assert el_registro.limpiar("Authorization: bearer abcdefghijklmnop.qrstu") == "Authorization: bearer ••••"
    ruta = str(Path.home() / "herramientas-ia" / "foto.jpg")
    limpio = el_registro.limpiar(f"No se pudo abrir {ruta}")
    assert limpio == "No se pudo abrir ~" + ruta[len(str(Path.home())) :] and str(Path.home()) not in limpio
    assert el_registro.limpiar("sin nada raro") == "sin nada raro"


def test_el_registro_no_escribe_trazas_con_rutas(clave_falsa, registros):
    try:
        raise ValueError(f"no se pudo leer {Path.home() / 'secreto.txt'} con {clave_falsa}")
    except ValueError:
        logging.getLogger("estudio").exception("Algo falló con la clave %s", clave_falsa)
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")
    registrado = "\n".join(registros.lineas)
    assert "Algo falló con la clave ••••" in registrado and "ValueError" in registrado
    assert "Exception in ASGI application" in registrado
    assert clave_falsa not in registrado and str(Path.home()) not in registrado
    assert "Traceback" not in registrado and "test_privacidad.py" not in registrado
