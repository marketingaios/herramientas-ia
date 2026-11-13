# Revisión de seguridad · Estudio de fotos de producto · versión 1

- **Fecha**: 13 de noviembre de 2026.
- **Quién revisa**: el Revisor, un subagente con el contexto limpio, que no escribe código. Leyó la ficha (puntos 1
  y 7), `AGENTS.md`, `PLAN.md`, el código y las pruebas. No cambió nada del repositorio: solo escribió este archivo.
- **Qué se revisó**: el commit `3010900` (rama `main`, 23 commits, sin cambios pendientes).
- **Cómo**: lectura del código; las pruebas rápidas (`uv run --directory estudio-fotos --group pruebas pytest`:
  pasaron las 695, en 7 min 50 s de reloj); comandos de solo lectura de git; y dos comprobaciones propias con la
  configuración de pruebas (carpeta temporal, sin internet, sin datos reales). Nunca se abrió el archivo `.env`.

Las rutas de este documento son relativas a `herramientas-ia/`; `estudio/…` y `pruebas/…` están dentro de
`estudio-fotos/`.

## Los 10 puntos de la ficha (punto 7)

| N.º | Punto | Estado |
|---|---|---|
| 1 | El servidor escucha solo en `127.0.0.1`, y una prueba lo comprueba | **Bien** |
| 2 | Ninguna clave en el código, el historial, los registros, las salidas, las respuestas ni los errores | **Bien** |
| 3 | `.env`, `modelos/`, `trabajo/`, `salidas/` y `gastos.jsonl` fuera de git | **Bien** |
| 4 | Dependencias con la versión fijada (`uv.lock`) | **Bien** |
| 5 | Subidas: tipo por contenido, tamaño, píxeles y nombres limpios | **Bien** (ver S1) |
| 6 | Las únicas conexiones son la descarga del modelo y openrouter.ai | **Bien** |
| 7 | Sin `shell=True`, `eval` ni `exec` con datos del usuario | **Bien** |
| 8 | Escribe solo dentro de `herramientas-ia`; `.env` con permisos 600 | **Bien** (ver S3) |
| 9 | La página no carga nada de internet | **Bien** (ver S4) |
| 10 | El recorte nunca usa `bria-rmbg` | **Bien** |

### Detalle

**1 · Solo `127.0.0.1` · Bien**

- Código: `estudio/__main__.py:19` fija la dirección; el enchufe se reserva ahí (`:41-47`) y uvicorn recibe ese
  enchufe ya reservado (`:117-123`). Buscado con grep en `estudio/*.py`: no hay otro `host=`, ni `0.0.0.0`, ni túneles.
- Prueba: `pruebas/test_arranque.py::test_arranca_escribe_la_direccion_y_responde_solo_en_este_computador` arranca el
  proceso de verdad y comprueba que no acepta conexiones por la dirección de la red local ni por IPv6;
  `pruebas/test_codigo.py::test_el_servidor_solo_escucha_en_este_computador` recorre el código. Lo comprueban de verdad.

**2 · Ninguna clave · Bien**

- Código: la clave solo se lee en `estudio/clave.py` y solo viaja en la cabecera de autorización de
  `estudio/openrouter.py:199-205`, sin seguir redirecciones. A la página solo va la máscara (`clave.py:35-37`); los
  errores de OpenRouter son textos fijos (`openrouter.py:22-33`); un fallo interno se anota solo con su tipo
  (`servidor.py:134-139`); `gastos.jsonl` lleva cinco campos (`costos.py:173-196`).
- Historial: `git log -p --all | grep -c "sk-or-"` da 17 líneas. Vistas con los textos largos tapados, son patrones
  de búsqueda, el texto de ayuda del campo y 7 claves de mentira de las pruebas, hechas con palabras (de 24 a 34
  caracteres). Ninguna tiene forma de clave. En el historial nunca hubo un archivo de claves (mirado por nombres).
- Pruebas: `test_privacidad.py::test_la_clave_no_aparece_en_ningun_sitio` (más de 50 respuestas, registros, consola,
  archivos de datos y lo enviado al simulador), `test_codigo.py::test_ningun_archivo_del_proyecto_lleva_una_clave` y
  `test_clave.py::test_la_pagina_solo_ve_la_mascara`. Lo comprueban de verdad. El historial no tiene prueba
  automática: vale la búsqueda de arriba.
- Salidas: `estudio-fotos/salidas/` y `trabajo/` están vacías y no existen `gastos.jsonl` ni `ajustes.json`.

**3 · Fuera de git · Bien**

- `.gitignore:2-3` (`.env`, `.env.*`), `:6` (`modelos/`), `:9-10` (`*/trabajo/`, `*/salidas/`), `:13-14`
  (`gastos.jsonl`). `git check-ignore -v` lo confirma ruta por ruta; `git ls-files` no lista ninguna; en el historial
  nunca se añadieron.
- Prueba: `test_estructura.py::test_git_deja_fuera_lo_privado` (llama a `git check-ignore` con 8 rutas) y
  `::test_gitignore_cubre_lo_pedido`.

**4 · Versiones fijadas · Bien**

- `estudio-fotos/pyproject.toml:7-16` y `:21-24`: todas con `==`. `uv.lock` está en git: 54 paquetes, todos del
  registro de PyPI, con 389 hashes sha256. `uv lock --check --offline` responde «Resolved 54 packages», código 0.
- Prueba: `test_estructura.py::test_todas_las_dependencias_tienen_la_version_fijada`.

**5 · Subidas · Bien**

- Tipo por contenido: `estudio/subidas.py:55-65`, y Pillow abre solo ese formato (`:104`). Tamaño: 25 MB por foto
  (`subidas.py:90-92`), 20 fotos (`servidor.py:271`) y el peso de la subida entera (`servidor.py:168-174`). Píxeles:
  50 megapíxeles, mirados en la cabecera antes de decodificar (`subidas.py:105-108`), y el tope de Pillow (`:23`).
  Nombres: `subidas.py:68-83`; el archivo se guarda con un nombre propio (`servidor.py:189-195`), nunca con el que llega.
- Pruebas: `test_subidas.py` (un PNG llamado `.jpg`, un texto llamado `.jpg`, 25 MB, 56 megapíxeles antes de
  decodificar, una bomba de 110 megapíxeles, 12 nombres con rutas) y
  `test_servidor.py::test_el_nombre_que_llega_nunca_se_usa_como_ruta`. Lo comprueban de verdad.
- El peso de la subida entera se puede saltar con una petición hecha a mano: es la sugerencia S1.

**6 · Conexiones · Bien**

- Solo `estudio/openrouter.py` usa una librería de red; la dirección es fija (`config.py:15`) y la variable de las
  pruebas solo admite `127.0.0.1` o `localhost`, y va junto con la carpeta temporal (`config.py:102-140`). El modelo
  lo descarga rembg de sus publicaciones en GitHub (`recorte.py:243-246`). La telemetría de FastAPI está apagada
  (`servidor.py:72`, `:216-218`) y en el entorno solo está la parte de OpenTelemetry que no envía nada.
- rembg 2.0.87 trae sesiones que mandan la foto a servicios de internet: la herramienta no puede llegar a ellas,
  porque solo admite los dos nombres de BiRefNet (`recorte.py:190-194`).
- Pruebas: `test_codigo.py::test_solo_el_cliente_de_openrouter_habla_con_internet`,
  `::test_las_unicas_direcciones_de_internet_del_codigo_son_las_de_openrouter` y
  `::test_la_telemetria_de_fastapi_esta_apagada`. La de punta a punta n.º 5 mira cada petición del navegador (no se
  pasó en esta revisión).

**7 · Sin `shell=True`, `eval` ni `exec` · Bien**

- Grep en `estudio/*.py`: nada de eso, ni `os.system` ni `pickle`. Se lanza un solo proceso (`equipo.py:253-257`): con
  lista de argumentos, sin intérprete de órdenes, con el nombre del modelo (de la lista fija) y rutas de la
  herramienta; su salida se descarta. En la página no hay `eval` ni `innerHTML`.
- Pruebas: `test_codigo.py::test_el_codigo_no_usa_nada_peligroso` y
  `test_pagina.py::test_el_codigo_de_la_pagina_escribe_los_datos_como_texto`.

**8 · Escribe solo dentro de `herramientas-ia`; `.env` con 600 · Bien**

- Todas las rutas salen de `config.py:17-87`; los temporales de las subidas van a `trabajo/` (`servidor.py:207`); los
  modelos, a `modelos/` (`recorte.py:174-183`). `.env`: se crea con 600 y se le vuelve a poner 600 después de cada
  escritura (`clave.py:96-111`).
- Comprobado: el `.env` real todavía no existe (nadie ha guardado una clave), así que los permisos se miraron en el
  código y en la prueba, no en el archivo. Las carpetas que rembg usa por su cuenta en la carpeta personal ya
  existían de antes y no tienen nada modificado hoy; no hay cachés de pooch ni de numba en la carpeta personal.
- Pruebas: `test_clave.py::test_el_env_queda_legible_solo_por_el_usuario` (600, también después de abrirlo a 644),
  `test_config.py::test_la_configuracion_normal_no_sale_de_herramientas_ia` y
  `test_recorte.py::test_los_modelos_van_a_la_carpeta_modelos_y_no_a_la_carpeta_personal`.
- Fuera queda solo lo del instalador (la caché de uv), anotado en `PLAN.md`, decisión 25.

**9 · La página no carga nada de internet · Bien**

- `estudio-fotos/web/index.html` solo carga de `/web/`, `/estilo/` y `/marca/`; los tres CSS no tienen `url(`, ni
  importaciones, ni fuentes de fuera (grep: 0); `app.js` solo llama a `/api/…`. La única dirección de fuera es el
  enlace de la firma: un enlace, no una carga. La política CSP solo deja archivos propios (`servidor.py:56-59`).
  `inicio/index.html` también carga solo archivos de la carpeta (mirado a mano).
- Pruebas: `test_pagina.py::test_la_pagina_no_carga_nada_de_internet`, `::test_la_pagina_cumple_su_politica_de_contenido`
  y `test_servidor.py::test_cada_respuesta_lleva_las_cabeceras_de_seguridad`.

**10 · Nunca `bria-rmbg` · Bien**

- Confirmado en el rembg instalado (2.0.87, `session_factory.py:11`): sin nombre usaría `bria-rmbg`. La herramienta
  tiene una sola llamada (`recorte.py:203`), siempre con el nombre ya comprobado (`recorte.py:190-194`); la descarga
  también va por nombre (`recorte.py:243-246`) y no se usa `remove()` de rembg.
- Pruebas: `test_recorte.py::test_el_codigo_solo_llama_a_rembg_por_una_puerta_y_con_nombre` y
  `::test_cualquier_otro_modelo_se_rechaza_antes_de_tocar_rembg`. Con el modelo real,
  `test_modelo_real.py::test_la_sesion_usa_el_modelo_pedido_por_su_nombre` (no se pasó en esta revisión).

## Otras observaciones

### Mirado y bien

- **Otra web abierta en el navegador** (peticiones cruzadas y cambio de DNS): `servidor.py:112-123` rechaza cualquier
  `Host` que no sea este computador, cualquier `Origin` que no sea la propia página y, en `/api/`, lo que el navegador
  marca como venido de otro sitio. Pruebas: `test_servidor.py::test_un_host_que_no_es_este_computador_se_rechaza` y
  `::test_otra_web_no_puede_usar_la_herramienta`.
- **Recorrido de rutas**: los archivos de la página (prueba con 8 rutas tramposas), los resultados solo por nombres
  anotados (`estudio.py:887-895`) y el ZIP solo con ids conocidos (`estudio.py:907-923`).
- **Inyección en la página**: todo se escribe con `textContent`; la política CSP no tiene excepciones.
- **Gasto sin confirmar**: `estudio.py:749-756` exige la confirmación y el costo que vio el usuario; el tope se mira
  antes de llamar y antes de cada imagen. Pruebas:
  `test_servidor.py::test_escenas_el_costo_se_ve_antes_y_solo_se_gasta_al_confirmar` y
  `::test_escenas_con_el_tope_superado_no_llaman_a_openrouter`.
- **Metadatos de las fotos** (GPS, autor): no pasan a los resultados
  (`test_privacidad.py::test_los_jpeg_no_llevan_los_metadatos_de_la_foto_original`).
- **Datos personales en los archivos de git**: ni rutas personales, ni el nombre de la cuenta, ni correos (grep).

### Hay que corregir

**C1 · gravedad media · la primera descarga del modelo escribe en la consola la ruta de la carpeta personal**

- Dónde: `estudio/recorte.py:243-246` y `estudio/registro.py:50-56`.
- Qué pasa: rembg descarga el modelo con pooch, y pooch tiene su propio registro, que escribe directo en la consola:
  «Downloading data from '…' to file '<carpeta personal>/herramientas-ia/modelos/models/…onnx'». El filtro de la
  herramienta, que cambia la carpeta personal por `~`, solo está puesto en los registros `estudio` y de uvicorn.
- Comprobado: el registro de pooch no lleva el filtro, y esa misma línea, emitida por ese registro, sale con la
  carpeta personal entera. La descarga de verdad no se repitió (no se usa internet en la revisión).
- Por qué importa: rompe una regla fija de la ficha (punto 1: en los registros, «ni rutas de la carpeta personal»).
  Le pasa a cada usuario nuevo en su primer recorte y, cuando el agente abre la herramienta en segundo plano, esa
  línea llega al agente. Ninguna prueba lo ve: usan el modelo ya descargado o lo descargan dentro de pytest.
- Por la misma causa, y menos probable: los avisos de Python de las librerías (llevan la ruta del archivo que avisa;
  rembg avisa si se pidió un acelerador y no quedó activo) y la traza de un error no controlado fuera de una
  petición (por ejemplo, si `crear_aplicacion` falla al arrancar, `__main__.py:115`).
- Qué hacer: que todo lo que llega a la consola pase por `registro.limpiar`: el registro de pooch (o dejarlo en
  avisos y errores), los avisos de Python (`logging.captureWarnings` con el filtro) y los errores no controlados
  (`sys.excepthook` y `threading.excepthook`, solo con el tipo). Añadir una prueba que emita por el registro de pooch
  una línea con la carpeta personal y compruebe que la consola no la lleva.

### Sugerencias (no bloquean)

- **S1 · baja · el tope de peso de la subida se puede saltar con una petición hecha a mano** (`servidor.py:168-174`).
  El tope se decide por el `Content-Length` que declara la petición. Comprobado: un logo de unos 8 MB enviado con
  `Content-Length: 10` y además `Transfer-Encoding: chunked` se recibe entero y se rechaza después («El logo pesa
  8,1 MB: el máximo es 5.»), en vez de rechazarse antes con el 413. Un navegador no puede enviar esa petición y otra
  web se rechaza antes: solo lo puede hacer un programa de este computador. Cada foto se sigue comprobando (25 MB) y
  los temporales se borran. Arreglo: contar los bytes mientras se reciben, o rechazar `Transfer-Encoding` en las
  subidas, y añadir el caso a `test_una_subida_que_pesa_demasiado_se_rechaza_antes_de_recibirla`.
- **S2 · baja · no hay contraseña local.** En un computador con varias cuentas abiertas a la vez, otra cuenta puede
  usar la herramienta mientras está abierta (subir el tope, gastar, borrar la clave); no puede leer la clave.
  Decirlo en el README o añadir un código de sesión.
- **S3 · baja · temporales del acelerador** (`equipo.py:248`). La carpeta temporal propia solo se le da al proceso de
  la prueba. Si la medición eligiera CoreML, el proceso principal prepararía el modelo sin ella y podría escribir en
  la carpeta temporal del sistema. Sin comprobar: aquí CoreML no terminó en 2 minutos y se usa el procesador.
  Arreglo: poner `TMPDIR` (y `TEMP`/`TMP` en Windows) en `trabajo/` al arrancar.
- **S4 · baja · `inicio/` no tiene prueba automática** de que no carga nada de internet (a mano, bien). Añadirla a
  `test_la_pagina_no_carga_nada_de_internet`.
- **S5 · baja, no es de seguridad · `trabajo/`.** Abrir una segunda copia vacía los temporales de la primera
  (`servidor.py:203`, `estudio.py:231-237`), y cada copia tiene su propio tope de sesión. Al cerrar, las fotos
  originales se quedan en `trabajo/` hasta el siguiente arranque: conviene vaciarla también al cerrar.
- **S6 · detalles** (leídos en el código, no ejecutados). `plataformas.py:10` y `:99`: `match` con `$` acepta un id
  con un salto de línea al final; mejor `fullmatch`. `escenas.py:115` y `ajustes.py:91`: si llega una lista donde va
  un texto, la respuesta es un 500 con el mensaje fijo (no cuenta nada); mejor un 400.

### Lo que no se pudo comprobar

- Las pruebas con el modelo real y las de punta a punta no se pasaron en esta revisión: vale lo anotado en
  `PRUEBAS.md`.
- Los permisos del `.env` real (todavía no existe) y el camino de Windows.
- OpenRouter de verdad: no se llamó ni se gastó nada.

## Veredicto de la primera vuelta

**Hay que corregir 1 punto.** Los 10 puntos de la ficha están «Bien».

1. **C1** (media): la consola no puede mostrar la ruta de la carpeta personal en la primera descarga del modelo, ni
   en los avisos de Python, ni en las trazas de errores no controlados. Con su prueba.

Las sugerencias S1 a S6 no bloquean la entrega. La S1 es la más recomendable: es un cambio pequeño y tiene prueba
fácil.

## Segunda vuelta

