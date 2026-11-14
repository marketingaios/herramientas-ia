# Revisión de seguridad · Estudio de fotos de producto · versión 1

- **Fecha**: 13 de noviembre de 2026.
- **Quién revisa**: el Revisor, un subagente con el contexto limpio, que no escribe código. Leyó la ficha (puntos 1
  y 7), `AGENTS.md`, `PLAN.md`, el código y las pruebas. No cambió nada del repositorio: solo escribió este archivo.
- **Qué se revisó**: el commit `3010900` (rama `main`, 23 commits, sin cambios pendientes).
- **Cómo**: lectura del código; las pruebas rápidas (`uv run --directory estudio-fotos --group pruebas pytest`:
  pasaron las 695, en 7 min 50 s de reloj); comandos de solo lectura de git; y dos comprobaciones propias con la
  configuración de pruebas (carpeta temporal, sin internet, sin datos reales). Nunca se abrió el archivo `.env`.
- **Estado**: cerrada en la segunda vuelta, sobre el commit `791461c`: **Aprobada** (ver «Veredicto final»).

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
· *Segunda vuelta: Corregido.*

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

Estado en la segunda vuelta: S1, **Corregido**; S2, **Avisado** en el README; S3, **Corregido** (sin comprobar con
CoreML de verdad); S4, **Corregido**; S5, **Corregido** el vaciado al cerrar y **Avisado** lo de una sola copia; S6,
**Corregido**. El detalle está en «Segunda vuelta».

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

- **Fecha**: 13 de noviembre de 2026.
- **Quién revisa**: el mismo Revisor, con las mismas reglas. No cambió código, pruebas ni configuración, no hizo
  commits, no usó internet, no gastó dinero y no abrió el archivo `.env`. Solo escribió en este archivo.
- **Qué se revisó**: el commit `791461c`, el único desde `3010900`. Solo lo corregido y sus pruebas: los 9 archivos de
  `estudio/` que cambiaron, las pruebas nuevas y lo que dicen `README.md`, `PLAN.md` (decisión 36) y `PRUEBAS.md`.
- **Cómo**: lectura de los cambios (`git diff 3010900 791461c`), las pruebas, y cinco comprobaciones propias sobre
  copias del proyecto en la carpeta temporal del Revisor (con la configuración de pruebas, sin datos reales).

### Estado de cada punto

| Punto | Estado |
|---|---|
| C1 · la consola y la carpeta personal | **Corregido** (quedan tres notas menores, N1 a N3) |
| S1 · subida «por trozos» | **Corregido** |
| S2 · sin contraseña local | **Avisado** en el README; sin cambio en el código |
| S3 · temporales del acelerador | **Corregido** en el código; sin comprobar con CoreML de verdad |
| S4 · prueba de `inicio/` | **Corregido** |
| S5 · `trabajo/` | **Corregido** el vaciado al cerrar; **Avisado** en el README lo de una sola copia |
| S6 · detalles | **Corregido** |

Nada quedó «Sin cambio» ni «Sigue mal».

**C1 · Corregido**

- Código: `estudio/registro.py:121-141` (`proteger_consola`) pone el filtro en el registro de pooch (`:85-96`), en el
  registro raíz, al que suben los registros de las librerías, y en la salida de los registros sueltos; manda los
  avisos de Python a ese registro; y cambia la traza de un error no controlado, en el hilo principal o en otro, por
  una línea con el tipo del error, el archivo (sin su carpeta) y la línea (`:99-118`). `estudio/__main__.py:100` lo
  llama antes que nada. `estudio/recorte.py:186` vuelve a poner el filtro de pooch justo antes de descargar o de
  preparar el modelo (`:203`, `:229`). La carpeta personal se tapa también escrita con «/» (`registro.py:27-34`).
- Comprobado por el Revisor: programas aparte que hacen lo mismo que el arranque (proteger la consola, crear el
  servidor de uvicorn, preparar los registros) y luego escriben por cada camino un texto con la carpeta personal. La
  línea de la descarga de pooch, un aviso de Python, un registro de una librería, un registro con traza (el de
  asyncio y el de uvicorn), un registro suelto, un error en otro hilo y un error no controlado en el hilo principal:
  en los ocho, la consola sale con `~` y sin traza.
- Pruebas: `test_privacidad.py::test_la_consola_no_muestra_la_carpeta_personal_por_ningun_camino`,
  `::test_el_registro_de_la_descarga_del_modelo_pasa_por_el_filtro`,
  `::test_la_carpeta_personal_se_tapa_tambien_escrita_con_barras_normales`,
  `::test_el_arranque_protege_la_consola_antes_que_nada` y
  `test_arranque.py::test_si_el_arranque_falla_la_consola_no_muestra_la_traza_ni_la_carpeta_personal`.
- ¿Fallarían sin el arreglo? Sí. Con el código de `3010900` fallan las cinco. Y quitando de una copia cada pieza del
  arreglo por separado (el filtro de pooch al arrancar, el de antes de descargar, los avisos de Python, el error en
  el hilo principal, el error en otro hilo, el registro raíz, los registros sueltos, la forma con «/» y la llamada
  del arranque), siempre falla al menos una.

**Otros caminos por los que la carpeta personal todavía puede llegar a la consola** (ninguno bloquea)

- **N1 · baja · errores que Python no puede lanzar** (`registro.py:139-140`). Un error dentro de un destructor
  (`__del__`) o al salir (`atexit`) lo escribe Python por `sys.unraisablehook`, que no se cambió: sale con su traza y
  sus rutas. Comprobado con un programa aparte, en los dos casos. Es poco probable: hace falta que una librería falle
  justo al soltar un objeto o al cerrar, y no se vio en ninguna pasada de las pruebas (la prueba del cierre exige que
  no haya traza). Arreglo: poner también `sys.unraisablehook` con el mismo mensaje y añadir el caso a la primera
  prueba de C1.
- **N2 · baja · Windows, sin comprobar de verdad** (`registro.py:27-34`). Simulado con una carpeta personal de
  mentira: la ruta normal y la escrita con «/» se tapan. No se tapa la escrita con las barras dobladas, que es como
  Python la pone dentro del texto de un error de archivo (el filtro añade ese texto cuando una librería registra un
  error con su traza, `registro.py:50-52`), ni la escrita con otras mayúsculas. Los registros de la herramienta solo
  escriben el tipo del error, así que solo afecta a los de las librerías. Arreglo: tapar también la forma con barras
  dobladas y, en Windows, comparar sin distinguir mayúsculas.
- **N3 · lo que no pasa por el filtro**. Lo que una librería escriba directo en la consola, sin usar los registros
  (comprobado: un `print` sale tal cual), y lo que escriba `uv` antes de arrancar la herramienta: su aviso cuando hay
  otro entorno de Python activado lleva la ruta de ese entorno (visto al pasar las pruebas). En las librerías que se
  usan no se vio ningún caso. Por eso la frase del README (`estudio-fotos/README.md:150-151`), «no muestra … la ruta
  de tu carpeta personal: tampoco … cuando algo falla», promete un poco más de lo que el código puede asegurar.

**S1 · Corregido**

- Código: `estudio/servidor.py:168-177`. Una subida que trae `Transfer-Encoding` se rechaza con el 411 antes de leer
  el cuerpo; sin esa cabecera, el servidor solo lee los bytes que declara `Content-Length`.
- Comprobado: repetida la comprobación de la primera vuelta. El logo de 8 MB con `Content-Length: 10` y
  `Transfer-Encoding: chunked` recibe ahora el 411 («La subida no dice cuánto pesa…»), sin recibirse entero y sin
  dejar temporales. Igual con solo `Transfer-Encoding`, con la cabecera en mayúsculas y en `/api/fotos`. Una subida
  normal sigue llegando. Las peticiones JSON no dependían de esto: cuentan los bytes al recibirlos
  (`servidor.py:142-150`).
- Prueba: `test_servidor.py::test_una_subida_que_pesa_demasiado_se_rechaza_antes_de_recibirla` (fotos y logo). Falla
  con el código anterior.

**S2 · Avisado en el README**

- `estudio-fotos/README.md:154-155`: la herramienta no pide contraseña; mientras está abierta, otro usuario o programa
  del computador podría usarla y gastar (ver la clave, no); conviene cerrarla al terminar. Dice lo que pasa de verdad.
  Sin cambio en el código (`PLAN.md`, decisión 36).

**S3 · Corregido en el código · sin comprobar con CoreML de verdad**

- Código: `estudio/equipo.py:185-203`. Si la medición eligió el acelerador, antes de preparar el modelo se crea
  `trabajo/acelerador` y `TMPDIR` apunta ahí. `TEMP` y `TMP`, los de Windows, no hacen falta: CoreML solo existe en Mac.
- Prueba, con piezas de mentira:
  `test_aceleracion.py::test_si_se_elige_el_acelerador_sus_temporales_van_a_la_carpeta_de_trabajo`. Falla con el
  código anterior.
- Sin comprobar: que CoreML escriba de verdad ahí. En este computador la medición deja el procesador.

**S4 · Corregido**

- Prueba nueva: `test_pagina.py::test_la_pagina_de_inicio_tampoco_carga_nada_de_internet`. Comprueba de verdad: exige
  que cada carga sea una ruta relativa a un archivo que existe dentro de la carpeta, y que los enlaces vayan solo a
  `127.0.0.1` o a la firma. Pasa también con el código anterior, como debe: la página ya estaba bien.

**S5 · Corregido (vaciar al cerrar) · Avisado (una sola copia)**

- Código: `estudio/servidor.py:212-217` vacía `trabajo/` al cerrar, después de parar el trabajo en curso;
  `estudio/estudio.py:231-244` ya no falla si falta la carpeta o si un archivo está en uso.
- Comprobado por el Revisor en una carpeta temporal: `trabajo/` queda vacía; un enlace puesto dentro de `trabajo/` se
  quita sin tocar lo que hay al otro lado; `salidas/` no se toca.
- Prueba: `test_arranque.py::test_al_cerrar_no_quedan_fotos_en_la_carpeta_de_trabajo` (con Ctrl+C y parada desde
  fuera): la foto subida desaparece de `trabajo/`, el resultado se queda en `salidas/` y no hay traza. Falla con el
  código anterior.
- Una sola copia a la vez: lo avisa `estudio-fotos/README.md:126-127`; sin cambio en el código. Ahora, además, cerrar
  una copia vacía los temporales de la otra: es el mismo caso y vale el mismo aviso. No es de seguridad.

**S6 · Corregido**

- Código: `estudio/plataformas.py:99` (`fullmatch`); `estudio/escenas.py:115` y `estudio/ajustes.py:91` (se mira que
  sea un texto antes de buscarlo).
- Pruebas: `test_plataformas.py::test_un_archivo_con_errores_da_un_mensaje_claro_y_sin_rutas` (el id con un salto de
  línea al final) y
  `test_servidor.py::test_una_lista_donde_va_un_texto_se_rechaza_con_su_mensaje_y_no_con_un_fallo_interno` (4
  casos). Fallan con el código anterior.

### ¿Las correcciones abrieron algo nuevo?

No se encontró nada.

- **Vaciar `trabajo/` al cerrar**: borra solo dentro de `trabajo/`, no sigue enlaces, y solo lo hace el servidor que
  creó su propio estudio (`servidor.py:203`, `:215`). Si un recorte sigue en marcha más de 10 segundos al cerrar, se
  queda sin su foto: se anota el tipo del error y el proceso termina igual.
- **Cambiar `TMPDIR` en el proceso**: solo pasa si la medición eligió el acelerador. Los temporales de las subidas no
  dependen de esa variable (`servidor.py:210`) y la prueba del acelerador recibe su propia carpeta (`equipo.py:261`).
  Si el acelerador fallara por quedarse sin esa carpeta (otra copia la vacía), el recorte sigue con el procesador
  (`estudio.py:345-356`).
- **El registro raíz con salida**: lo que las librerías registran como aviso o error ya llegaba a la consola; ahora
  pasa por el filtro. No sale nada que antes no saliera.
- **Los errores no controlados** no se esconden: queda una línea con el tipo y el lugar, y el proceso sigue
  terminando con error (la prueba del arranque roto lo exige).
- **Rechazar `Transfer-Encoding`**: la página sube con el peso declarado. La prueba de punta a punta n.º 1 sube 5
  fotos con Chromium y pasa.
- **`pruebas/conftest.py`**: solo devuelve `TMPDIR` a su valor después de cada prueba.
- Después de todas las pasadas: `salidas/` y `trabajo/` reales siguen vacías, no hay `gastos.jsonl` ni
  `ajustes.json`, el archivo `.env` sigue sin existir y sigue fuera de git, y el código y las pruebas están igual
  que en `791461c` (`git diff` vacío en `estudio/` y `pruebas/`).

### Pruebas que se pasaron

| Qué | Resultado |
|---|---|
| Rápidas, sobre `791461c` (`uv run --directory estudio-fotos --group pruebas pytest`) | 712 pasan, ninguna falla; 1 min 01 s |
| Con el modelo real (`-m modelo`) | 9 pasan; 3 min 08 s |
| De punta a punta (`-m e2e`) | 5 pasan; 46 s |
| Las 16 pruebas de lo corregido (15 nuevas y la de S1, ampliada), con el código de `3010900`, en una copia | 14 fallan; pasan la de S4 y un caso de S6 que ya se rechazaba |
| Las 5 pruebas de C1, quitando una pieza del arreglo cada vez (9 veces), en una copia | siempre falla al menos una |
| `test_estructura.py` y `test_codigo.py`, después de escribir esta sección | 64 pasan |

Las pruebas con el modelo real no descargaron nada: el modelo ya estaba en `modelos/`. Las de punta a punta usan
OpenRouter simulado.

### Lo que sigue sin poder comprobarse

- La primera descarga del modelo, mirando la consola de verdad: no se usa internet y el modelo ya está descargado.
  Vale la comprobación hecha con el mismo registro que usa la descarga.
- El acelerador con CoreML de verdad (S3): aquí la medición volvió a dejar el procesador.
- Windows y Linux: N2 es una simulación.
- Los permisos del `.env` real: todavía no existe.
- OpenRouter de verdad: no se llamó ni se gastó nada.

### Cambios que aparecieron al cerrar la revisión (fuera de lo revisado)

Al terminar esta sección había en la carpeta de trabajo, sin commit, tres cambios de documentos que no hizo el Revisor
(él solo escribe este archivo):

- `README.md`: la frase de N3 ya está cambiada. Ahora dice que lo que escribe la herramienta pasa por un filtro que
  tapa la clave y la carpeta personal, y que lo que escriba `uv` antes de arrancarla no pasa por él. Se ajusta más a
  lo que hace el código. N1 y N2 siguen igual.
- `PRUEBAS.md`: anota las tres pasadas del Revisor, con los mismos números de la tabla de arriba.
- `CAMBIOS.md`: deja N1, N2 y lo que no se probó para la versión siguiente.

Leídos con `git diff`: son solo texto, no tocan código ni pruebas, y no cambian el veredicto. Los números de línea
del README que cita esta sección son los del commit `791461c`.

## Veredicto final

**Aprobada.**

- C1 está corregido y sus pruebas fallan sin el arreglo. Las seis sugerencias quedaron corregidas o avisadas.
- Los 10 puntos de la ficha siguen «Bien»: lo cambiado toca los puntos 5, 8 y 9 y los deja mejor, y las 726 pruebas
  pasan (712 rápidas, 9 con el modelo real y 5 de punta a punta).
- No queda nada que corregir para entregar la versión 1.
- Para una versión siguiente, sin urgencia: N1 (`sys.unraisablehook`, en `estudio/registro.py:139-140`) y N2 (la
  carpeta personal como la escribe Windows, en `estudio/registro.py:27-34`). La frase del README de N3
  (`estudio-fotos/README.md:150-151`) ya está cambiada en la carpeta de trabajo, sin commit todavía.

# Revisión de seguridad · versión 1.1

- **Fecha**: 14 de noviembre de 2026.
- **Quién revisa**: el Revisor, un subagente con el contexto limpio, que no escribe código. Solo escribió esta sección:
  no cambió código, pruebas ni configuración, no hizo commits, no arrancó la herramienta de verdad, no llamó a
  OpenRouter, no gastó dinero y no abrió el archivo de la clave.
- **Qué se revisó**: la rama `version-1.1` en el commit `39f999f` (10 commits desde `main`, sin cambios pendientes),
  contra los puntos 1, 4.7, 7 y 13 de la ficha. Es una revisión corta: solo los puntos que tocan los cambios de la 1.1.
- **Cómo**: lectura del código y de `git diff main..HEAD` (no de lo que dicen los documentos ni los mensajes de los
  commits); las tres baterías de pruebas, una cada vez; comandos de solo lectura de git; y comprobaciones propias con
  datos de mentira en la carpeta temporal de las pruebas (`estudio-fotos/.pruebas-tmp/`, fuera de git).
- **Veredicto**: **Aprobada**, con dos sugerencias que no bloquean (el detalle, al final).

Las rutas son relativas a `herramientas-ia/`; `estudio/…` y `pruebas/…` están dentro de `estudio-fotos/`.

## Los puntos que tocan los cambios

| N.º | Punto | Estado |
|---|---|---|
| 9 | La página no carga nada de internet, tampoco las fuentes | **Bien** |
| 8 | Escribe solo dentro de `herramientas-ia` (la limpieza al arrancar) | **Bien** (ver S1) |
| 5 | Subidas, ya sin la del logo | **Bien** |
| 2 | Ninguna clave | **Bien** |
| 3 | Fuera de git lo que debe estarlo | **Bien** (ver S2) |
| 6 | Conexiones, y el color que viaja a OpenRouter | **Bien** |
| 1, 4, 7 y 10 | El diff no los toca | **Bien**, sin cambios |

**9 · La página no carga nada de internet, tampoco las fuentes · Bien**

- La herramienta: `estudio-fotos/web/index.html:7-10` carga el icono, las dos hojas y el programa desde `/marca/`,
  `/estilo/` y `/web/`; las imágenes fijas son el logo de Ismagit (`:16`, `:263`). `web/app.css` no tiene ningún
  `url(` ni importaciones, y `web/app.js` tiene una sola llamada `fetch` (`:43`), siempre a rutas `/api/…`, de donde
  salen también las fotos que pinta. La única dirección de fuera es el enlace de la firma (`:262`): se pulsa, no se
  carga.
- Las fuentes: `estilo/estilo.css:7-45` tiene cuatro reglas `font-face`, y sus cuatro `url(` son los únicos de las
  tres hojas: `fuentes/geist-….woff2`, rutas relativas a archivos de `estilo/fuentes/`. Mirado: los cuatro son WOFF2
  de verdad, iguales byte a byte a los de `marca/fuentes/`, con su `OFL.txt` al lado, y en `estilo/`, `marca/`, `web/`
  e `inicio/` no hay enlaces simbólicos. Detrás de Geist solo van fuentes del sistema (`estilo/estilo.css:65-66`).
- La página de inicio: `inicio/index.html:7-8`, `:14` y `:45` cargan `../estilo/estilo.css`, `inicio.css` y
  `../marca/ismagit_logo.png`; no lleva programa. `inicio/inicio.css` no tiene `url(`. `estilo/firma.html:5-6`, igual.
- El servidor: la política CSP no cambió (`estudio/servidor.py:54-57`: todo `'self'`, también `font-src`) y va en
  todas las respuestas (`:101-112`). `/web/`, `/estilo/` y `/marca/` salen por `StaticFiles` (`:257-259`). La 1.1 solo
  añade `Cache-Control: no-cache` a `/web/` y `/estilo/` (`:108-111`).
- Comprobado por el Revisor, llamando a la aplicación (sin abrir ningún puerto) sobre una copia de `estilo/` y
  `marca/` con trampas dentro: las fuentes salen como `font/woff2`, con la CSP entera y `nosniff`; y 29 rutas tramposas
  dan todas 404 sin soltar nada de fuera (enlaces simbólicos puestos dentro de `estilo/`, `estilo/fuentes/` y `marca/`
  que apuntan fuera, rutas con `..` escritas de varias formas, rutas absolutas, y las demás carpetas de
  `herramientas-ia`). Por `/marca/` salen también los otros dos logos de Ismagit y la copia de las fuentes, que
  ninguna página usa: no tienen nada privado.
- Pruebas (leídas: comprueban de verdad): `pruebas/test_pagina.py::test_la_pagina_no_carga_nada_de_internet` y
  `::test_la_pagina_de_inicio_tampoco_carga_nada_de_internet`;
  `pruebas/test_diseno.py::test_las_fuentes_solo_se_cargan_de_estilo_fuentes` (una lista blanca);
  `pruebas/test_servidor.py::test_los_archivos_de_la_pagina_son_locales` y
  `::test_no_se_puede_salir_de_las_carpetas_de_la_pagina`. En el navegador, el recorrido 5 de `pruebas/test_e2e.py`
  exige que Geist y Geist Mono queden cargadas desde `/estilo/fuentes/`, y
  `::test_6_la_pagina_no_cargo_nada_de_internet_ni_dio_errores`, que cada petición vaya a este computador y que la
  consola quede sin errores.

**8 · Escribe solo dentro de `herramientas-ia` · Bien**

- Código: `estudio/ajustes.py:55-79` (`limpiar_version_1`). Toca dos rutas y nada más, las dos sacadas de la
  configuración (`estudio/config.py:61-68`: `ajustes.json` y `logo_negocio.png`, en la carpeta de datos, que es
  `estudio-fotos/`). Se llama una vez, al arrancar de verdad (`estudio/servidor.py:207-210`, por
  `estudio/estudio.py:246-248`). No busca por la carpeta, no borra carpetas y no registra nada.
- `ajustes.json` solo se vuelve a escribir si se lee bien, es un objeto y trae campos de más; se escribe en un
  temporal de la misma carpeta y se cambia de una vez (`estudio/ajustes.py:47-52`). El logo se borra con un solo
  `unlink` (`:77`).
- Comprobado por el Revisor, en 11 casos: si `ajustes.json` es un enlace a un archivo de fuera, lo de fuera queda
  intacto y el enlace pasa a ser un archivo normal con los tres ajustes. Un enlace roto, un enlace a una carpeta, una
  carpeta y un archivo con BOM no se tocan. Si el logo es un enlace a una carpeta de fuera, se quita solo el enlace;
  si es una carpeta con cosas, se queda. Con la carpeta de solo lectura no falla, no cambia nada y no deja restos. Un
  archivo vecino (`logo_negocio.png.bak`) no se toca. Los valores raros (un número donde va un texto, `NaN`) se
  conservan tal cual, y al cargarlos valen los de fábrica. Queda un caso sin cubrir: es la sugerencia S1.
- Pruebas: las del paso 27 en `pruebas/test_ajustes.py` (la carpeta de la versión 1 entera, la segunda arrancada sin
  cambios, 9 archivos rotos o ya limpios, el logo que no se puede borrar, el logo que es un enlace) y
  `pruebas/test_arranque.py::test_al_arrancar_se_quita_la_marca_del_negocio_que_dejo_la_version_1`, con el proceso de
  verdad. El vigilante de `pruebas/conftest.py:57-87` mira también el `logo_negocio.png` real.
- Los archivos reales, antes y después de todas las pasadas: `ajustes.json`, `gastos.jsonl`, `logo_negocio.png` y
  `medicion.json` tienen el mismo tamaño, la misma fecha y la misma huella; `salidas/` sigue con sus 22 archivos sin
  tocar; y el archivo de la clave, con el mismo tamaño y la misma fecha (en el listado de la carpeta se ve con
  permisos 600; no se abrió). `ajustes.json` y `logo_negocio.png` siguen como los dejó la versión 1: la limpieza los
  cambiará la primera vez que se abra la 1.1, como avisan el README y `CAMBIOS.md`.

**5 · Subidas · Bien**

- `estudio/subidas.py` no cambió (tipo por el contenido, 25 MB, píxeles, nombres sin rutas), y la entrada de las
  fotos sigue entera: solo el campo `fotos` (`estudio/servidor.py:182-192`), el peso mirado antes de recibir
  (`:170-179`), un nombre propio en el disco (`:195-201`) y hasta 20 fotos (`:273-289`).
- La subida del logo se quitó entera: no quedan sus tres rutas, ni `guardar_logo`, `quitar_logo` y el tope del logo,
  ni su campo en la página, donde el único campo de archivo es el de las fotos (`web/index.html:45`). Buscado con grep
  en `estudio/` y `web/`: no hay código a medias. Comprobado: `GET /api/logo` y `GET`, `POST` y `DELETE
  /api/ajustes/logo` dan 404.
- Pruebas: `pruebas/test_servidor.py::test_las_rutas_del_logo_ya_no_existen`,
  `pruebas/test_ajustes.py::test_el_estudio_ya_no_guarda_ni_sirve_ningun_logo`, y las de `pruebas/test_subidas.py` y
  de la subida «por trozos», que siguen pasando.

**2 · Ninguna clave · Bien**

- El diff no toca `estudio/clave.py`, `estudio/openrouter.py` ni `estudio/registro.py`. Lo nuevo no registra nada (la
  limpieza), y el error del color es un mensaje fijo.
- Historial: `git log -p main..HEAD` tiene 2 líneas con el patrón de las claves de OpenRouter, que son una
  comprobación de una prueba y el texto de ayuda del campo de la clave, que ya estaba. En todo el historial son 21
  (19 de `main`): patrones de búsqueda, ese texto de ayuda y claves de mentira hechas con palabras. Lo más largo mide
  34 caracteres, y ninguna tiene forma de clave (ninguna con 40 caracteres seguidos o más).
- Una clave no puede viajar donde va el color: `pruebas/test_privacidad.py::test_la_clave_no_aparece_en_ningun_sitio`
  envía la clave falsa como color a las dos rutas de escenas, recibe un 400 que no la repite y comprueba que no se
  llamó a nadie. El recorrido 6 de punta a punta mira que la salida del servidor no lleve la clave ni el color.

**3 · Fuera de git · Bien**

- `.gitignore` no cambió en la 1.1 (`:2-3`, `:6`, `:9-10`, `:13-17`). `git check-ignore` confirma, ruta por ruta,
  `ajustes.json`, `gastos.jsonl`, `medicion.json`, `logo_negocio.png`, `salidas/`, `trabajo/`, `modelos/`,
  `.pruebas-tmp/` y `.navegadores/`. `git ls-files` (84 archivos) no lista ninguno, y en el historial nunca entraron
  (mirado por nombres). Después de las pruebas, `git status` sigue limpio.
- Lo que la 1.1 metió en git: las 4 fuentes con su licencia (dos veces, en `marca/fuentes/` y en `estilo/fuentes/`),
  `marca/ismagit_logo.png`, 4 fotos de muestra y `pruebas/test_diseno.py`. Mirados los binarios: son lo que dicen ser
  (WOFF2, PNG, JPEG). Las fotos y los logos no llevan GPS ni autor en sus metadatos, ni rutas personales ni el nombre
  de la cuenta dentro; las fuentes van comprimidas y no se miraron por dentro (son las de la guía). En las líneas que
  añade la rama no hay rutas personales ni correos. El repositorio no tiene remotos.

**6 · Conexiones, y el color que viaja a OpenRouter · Bien**

- La 1.1 no añade ninguna librería de red ni ninguna dirección: `estudio/openrouter.py` no cambió, y la única
  dirección de internet a la que llama el código sigue siendo la de OpenRouter (`estudio/config.py:15`).
- El color llega por `web/app.js:464` y `estudio/servidor.py:357-376`, y antes de usarse pasa por `validar_color`
  (`estudio/escenas.py:118-128`): solo vale un texto que sea, entero, `#` y seis cifras hexadecimales (`:61`, con
  `fullmatch`); si no llega, gris claro. Se comprueba con cualquier escena, y antes de estimar, de mirar la clave y de
  llamar a nadie (`estudio/estudio.py:690-695`, `:711`, `:746`). Solo entra en el texto de «Fondo liso de un color» y
  en el título de esa escena (`estudio/escenas.py:145-146`).
- No va al nombre del archivo (`estudio/escenas.py:276` usa el id, `fondo-liso`), ni a `gastos.jsonl`, ni a
  `resumen.csv`, ni a los registros. En la página, el título se escribe como texto (`web/app.js:603-617`).
- Comprobado por el Revisor: 22 valores raros (un salto de línea delante o detrás, espacios, cifras de otros
  alfabetos, 5 o 7 cifras, un carácter nulo, una frase detrás del color, otros tipos) dan todos el mensaje fijo;
  `#a1b2c3` sale como `#A1B2C3`, y solo en esa escena.
- Pruebas: `pruebas/test_escenas.py::test_un_color_que_no_es_un_color_no_vale_con_ninguna_escena` y
  `pruebas/test_servidor.py::test_un_color_que_no_vale_da_su_mensaje_en_las_dos_rutas_con_cualquier_escena`.

**1, 4, 7 y 10 · sin cambios**

- **1**: `estudio/__main__.py` no cambió: sigue solo en `127.0.0.1`.
- **4**: `pyproject.toml` y `uv.lock` solo cambian la versión del proyecto (de 1.0.0 a 1.1.0): ninguna dependencia.
- **7**: en lo añadido a `estudio/` y `web/` no hay `shell=True`, `eval`, `exec`, procesos nuevos ni `innerHTML`.
- **10**: `estudio/recorte.py` no cambió.

## Los seis cambios del punto 13 (observaciones, fuera de la seguridad)

Mirados en el código y en las páginas: los seis están hechos como dice la ficha.

- **1 · Diseño**: las 11 variables con sus valores exactos (`estilo/estilo.css:49-59`), Geist local, el logo de 28 px
  con «Estudio de fotos» (`web/index.html:16-17`) y la firma. La página no se miró a ojo: vale el recorrido 5.
- **2 · Sin marca del negocio**: quedan tres ajustes (`estudio/ajustes.py:17-22`), el estado ya no trae `negocio`
  (comprobado) y nada de lo que llega del servidor cambia los colores (`web/app.js:104-110`).
- **3 · Escenas**: `estudio/escenas.py:39-44` y el selector de color (`web/index.html:131-136`).
- **4 · Muestras**: las cuatro fotos nuevas están, y las pruebas usan las que haya (`pruebas/conftest.py:41-46`).
- **5 · Mac y Windows**: `estudio-fotos/README.md:3`. **6 · Versión**: `estudio-fotos/CAMBIOS.md:3`, `AGENTS.md:38` e
  `inicio/index.html:34`.

Restos del negocio de ejemplo de la versión 1:

- En el código, las pruebas, las páginas y los documentos no queda nada (grep propio y
  `pruebas/test_estructura.py::test_no_queda_el_negocio_de_ejemplo_de_la_version_1`). De la marca del negocio solo
  quedan la limpieza y la ruta del logo antiguo (`estudio/config.py:66-68`), que hacen falta para quitarla.
- Dos fotos de `muestras/` que se quedan, `bolsa_mesa.jpg` y `taza_logo.jpg`, enseñan su marca en el producto
  (miradas). `PLAN.md` (apartado 8.3, decisión 13) dice que son de la guía 1.1 y que se quedan: lo decide el dueño.
- El historial de git conserva su logo y sus tres fotos: no se reescribe (la misma decisión).
- Los apartados 1 a 7 de `PLAN.md` y los pasos antiguos de `TAREAS.md` siguen hablando de la marca del negocio y de
  las rutas del logo: son el plan de la versión 1, y el apartado 8.1 dice qué ya no vale.

## Sugerencias (no bloquean)

- **S1 · baja · un `ajustes.json` con muchísimos niveles impide arrancar** (`estudio/ajustes.py:34` y `:69`).
  Comprobado: con 200.000 corchetes abiertos, `cargar` y `limpiar_version_1` lanzan `RecursionError`, que no es
  ninguno de los dos errores que se atrapan. Deducido del código, sin arrancar: `estudio/estudio.py:209` llama a
  `cargar` sin protección, así que la herramienta no arrancaría. Ya pasaba en la versión 1 con `cargar`; la 1.1
  repite el mismo `except` en la limpieza. No se puede provocar desde la página (el servidor solo escribe los tres
  ajustes ya comprobados): hay que escribir el archivo a mano. Arreglo: atrapar también `RecursionError` en los dos
  sitios y añadir el caso a la prueba de los archivos rotos.
- **S2 · baja · el temporal de `ajustes.json` no está en `.gitignore`** (`estudio/ajustes.py:50`, `.gitignore:15`).
  Al guardar se escribe primero `ajustes.json.tmp-N` (N es el número del proceso), y `git check-ignore` dice que ese
  nombre no está ignorado. Supuesto, sin reproducir: si la escritura se corta a medias, git vería ese archivo. Con la
  1.1 solo llevaría los tres ajustes, sin datos del negocio, y en los casos del Revisor no quedó ningún resto.
  Arreglo: una línea `*/ajustes.json.tmp-*` en `.gitignore`.

## Pruebas pasadas

Desde `herramientas-ia`, una batería cada vez, sobre el commit `39f999f`:

| Batería | Resultado | Tarda |
|---|---|---|
| Rápidas (`uv run --directory estudio-fotos --group pruebas pytest`) | 830 pasan, ninguna falla | 1 min 35 s |
| Con el modelo real (`-m modelo`) | 10 pasan | 5 min 45 s |
| De punta a punta (`-m e2e`) | 6 pasan | 4 min 54 s |
| **Total** | **846 pasan** | |
| Rápidas otra vez, después de escribir esta sección (una prueba vigila los documentos) | 830 pasan | 2 min 02 s |

Todas pasaron a la primera: no hubo que repetir ninguna. Los tiempos salen más altos que en `PRUEBAS.md` porque el
computador estaba ocupado con otros trabajos. Las pruebas con el modelo real no descargaron nada (en `modelos/` no
cambió ningún archivo) y las de punta a punta usan OpenRouter simulado.

## Lo que no se pudo comprobar

- El arranque de verdad sobre los datos reales: no se arrancó la herramienta. La limpieza se probó con copias y con
  datos de mentira, nunca con el `ajustes.json` ni el `logo_negocio.png` reales.
- La página a ojo, en una pantalla: valen las pruebas de punta a punta.
- OpenRouter de verdad: no se llamó ni se gastó nada. No se sabe cómo pinta el modelo el color pedido.
- Windows y Linux, y otros navegadores: los enlaces y los permisos se probaron solo en este Mac, y la página, solo
  en Chromium. La página de inicio abierta como archivo en otro navegador no se probó: si no cargara Geist, se vería
  con la fuente del sistema.
- El contenido del archivo de la clave: nunca se abrió.

## Veredicto

**Aprobada.**

- No hay nada que corregir: ningún punto «Hay que corregir». Los puntos 9, 8, 5, 2, 3 y 6 están «Bien», y el diff no
  toca el 1, el 4, el 7 ni el 10.
- Pasan las 846 pruebas (830 rápidas, 10 con el modelo real y 6 de punta a punta).
- Las sugerencias S1 y S2 son de gravedad baja y no bloquean la entrega: pueden ir en esta versión o en la siguiente.

## Segunda vuelta

- **Fecha**: 14 de noviembre de 2026.
- **Quién revisa**: el mismo Revisor, con las mismas reglas. Solo añadió este apartado.
- **Qué se revisó**: el commit `be17584`, el único desde `39f999f`: solo lo corregido (S1 y S2) y sus pruebas. Cambia
  `.gitignore`, `estudio/ajustes.py`, `pruebas/test_ajustes.py` y `pruebas/test_estructura.py`; esta sección entró en
  el commit tal como la dejó la primera vuelta (la misma huella).
- **Cómo**: `git show be17584`, lectura del código, las tres baterías otra vez y comprobaciones propias con datos de
  mentira en `estudio-fotos/.pruebas-tmp/`, comparando con el código de `39f999f` cargado en memoria.

| Punto | Estado |
|---|---|
| S1 · un `ajustes.json` con muchísimos niveles | **Corregido** lo anotado (al leer); queda un caso vecino, de gravedad baja: N1 |
| S2 · el temporal de `ajustes.json`, fuera de git | **Corregido** |

**S1 · Corregido (al leer)**

- Código: `estudio/ajustes.py:34` (`cargar`) y `:69` (`limpiar_version_1`) atrapan también `RecursionError`.
- Comprobado: con 100.000 y 200.000 corchetes abiertos, y con la marca con 100.000 niveles, el código de `39f999f`
  lanza `RecursionError` en las dos funciones. El de `be17584` no lanza nada, no toca el archivo, borra el logo, y
  `cargar` da los ajustes de fábrica.
- Pruebas: dos casos nuevos de
  `pruebas/test_ajustes.py::test_un_ajustes_json_roto_o_ya_limpio_no_se_toca_y_no_impide_arrancar` (`:240-242`):
  `demasiados-niveles` y `la-marca-con-demasiados-niveles`. Con el código anterior fallan (comprobado con sus mismos
  contenidos).

**N1 · baja · el mismo error, al volver a escribir** (`estudio/ajustes.py:72-75`)

- No lo abrió la corrección: con el código de `39f999f` pasa igual (comprobado). Es la otra mitad de S1, que el
  Revisor no vio en la primera vuelta.
- Qué pasa: si `ajustes.json` se lee bien, trae campos de marca y, además, uno de los tres ajustes lleva un valor
  con entre unos 1.000 y unos 10.000 niveles, la limpieza intenta escribirlo «tal como estaba», y la escritura
  (`guardar`, `:51`) lanza `RecursionError`. Ahí solo se atrapa `OSError` (`:74`).
- Comprobado: con 1.000, 1.100, 2.000 y 5.000 niveles en `calidad_recorte`, y con 2.000 en `modelo_escenas`,
  `limpiar_version_1` lanza `RecursionError`; el archivo queda igual, no queda ningún temporal y el logo no se borra.
  En este computador (Python 3.12.13) la escritura falla desde 995 niveles y la lectura aguanta hasta 9.996. Por el
  camino del arranque, con datos de mentira: el estudio se crea bien (ese valor queda como de fábrica) y la limpieza
  lanza el error. Deducido del código, sin arrancar: la herramienta no arrancaría, porque
  `estudio/servidor.py:207-210` no lo protege.
- Cuándo no pasa: con 10.000 niveles o más lo para la lectura, que es lo corregido; y si lo profundo está solo en un
  campo de marca, ese campo no se escribe.
- Por qué es baja: como S1, no se puede provocar desde la página (ni la versión 1 ni la 1.1 guardan nunca un valor
  así: los tres ajustes se comprueban antes de guardarse). Hay que escribir el archivo a mano, y basta arreglarlo o
  quitarlo para que arranque.
- Arreglo: atrapar también `RecursionError` en `estudio/ajustes.py:74`, y añadir a la prueba de los archivos rotos
  un caso con la marca y unos 2.000 niveles en uno de los tres ajustes.

**S2 · Corregido**

- `.gitignore:16`: `*/ajustes.json.tmp-*`. `git check-ignore -v` lo confirma con `estudio-fotos/ajustes.json.tmp-123`.
  No cubre de más: otros nombres parecidos y los archivos del proyecto siguen sin ignorar, y ningún archivo que git
  ya seguía queda ahora ignorado (`git ls-files -ci --exclude-standard` no lista nada).
- Prueba: `pruebas/test_estructura.py::test_git_deja_fuera_lo_privado`, con el caso nuevo (`:90`), que llama a
  `git check-ignore`: sin esa línea de `.gitignore`, falla.

### ¿Las correcciones abrieron algo nuevo?

No se encontró nada.

- Atrapar `RecursionError` al leer no esconde otra cosa: el archivo se trata como roto, igual que los demás casos, y
  no se toca.
- La línea nueva de `.gitignore` solo cubre ese nombre.
- Dos notas de documentos, que no bloquean. Con los 3 casos nuevos, las rápidas son 833 y el total 849: `PRUEBAS.md`
  sigue con 830 y 846, que son los números de antes de la revisión (y así lo dice). Y los números de línea de
  `.gitignore` que cita la primera vuelta son los de `39f999f`: en `be17584`, desde la 16, van una línea más abajo.
- Después de todas las pasadas, los archivos reales (`ajustes.json`, `gastos.jsonl`, `logo_negocio.png`,
  `medicion.json`, `salidas/` y el archivo de la clave, que no se abrió) siguen con el mismo tamaño y la misma fecha,
  y `git status` está limpio.

### Pruebas pasadas, sobre `be17584`

Una batería cada vez, todas a la primera:

| Batería | Resultado | Tarda |
|---|---|---|
| Rápidas (`uv run --directory estudio-fotos --group pruebas pytest`) | 833 pasan, ninguna falla | 1 min 10 s |
| Con el modelo real (`-m modelo`) | 10 pasan | 3 min 25 s |
| De punta a punta (`-m e2e`) | 6 pasan | 59 s |
| **Total** | **849 pasan** | |
| Rápidas otra vez, después de escribir este apartado | 833 pasan | 1 min 11 s |

### Lo que sigue sin poder comprobarse

Lo mismo que en la primera vuelta: el arranque de verdad sobre los datos reales, la página a ojo, OpenRouter de
verdad, Windows y Linux y otros navegadores. De N1, el número exacto de niveles depende de la versión de Python: se
midió solo en este computador.

### Veredicto final

**Aprobada.**

- S1 (lo anotado) y S2 están corregidas, y sus pruebas fallan sin el arreglo.
- N1 es de gravedad baja y no bloquea: es el mismo arreglo de una línea que S1, y puede ir en esta versión o en la
  siguiente.
- Los puntos de la ficha que tocan los cambios siguen «Bien», y pasan las 849 pruebas (833 rápidas, 10 con el modelo
  real y 6 de punta a punta).

