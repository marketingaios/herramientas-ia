# Plan · Estudio de fotos de producto · versión 1

Plan del Constructor para la ficha 1 (`FICHA.md`). Computador de construcción: Mac con chip Apple (arm64), uv 0.11.8,
git 2.50.1. Segunda versión del plan: incluye las correcciones del Revisor (apartado 7).

El plan corto de la **versión 1.1** (ficha 1.1, punto 13) está en el apartado 8: dice qué cambia de este plan.

## 1. Arquitectura

Una sola aplicación local: un servidor FastAPI en `http://127.0.0.1:8601` que sirve una página estática (HTML, CSS y
JavaScript sin compilar) y una API JSON. Todo el trabajo con imágenes pasa en el computador; la única llamada a
internet en uso normal es a OpenRouter, y solo después de que el usuario confirma (el gasto) o pulsa Probar (la clave).

```
navegador (página estática)  ──HTTP solo 127.0.0.1──▶  servidor FastAPI
   Fotos · Resultados · Ajustes                          │
   consulta /api/estado cada 0,7 s                       ├─ subidas: valida y guarda en trabajo/
                                                         ├─ cola de recorte (1 hilo) ── rembg + BiRefNet (modelos/)
                                                         ├─ medidas: fondo blanco, encuadre, JPEG ── salidas/
                                                         ├─ escenas: httpx ──▶ openrouter.ai (solo con confirmación)
                                                         ├─ ajustes.json · .env (solo la línea de la clave)
                                                         └─ gastos.jsonl · ZIP · resumen.csv
```

- **Estado**: en memoria, protegido con un candado. La página lo lee entero con `GET /api/estado` (sondeo simple; sin
  websockets). Recargar la página no pierde nada; reiniciar el servidor empieza una sesión nueva.
- **Trabajos en lote**: tres tipos (recorte, medidas, escenas), cada uno con `total`, `hechos`, el archivo actual, los
  segundos y los mensajes. El recorte tiene una cola con un solo hilo, que crea la sesión de rembg una vez y la
  reutiliza en todo el lote. Un error en una foto no rompe el lote.
- **Archivos**: `trabajo/<id>/` guarda la subida y las vistas previas (se vacía al arrancar); `salidas/<fecha_hora>/`
  guarda los resultados de cada sesión (`recortes/`, `<plataforma>/`, `escenas/`), así nunca se pisa una sesión
  anterior. «Empezar de nuevo» vacía la lista de fotos, no borra `salidas/`.
- **Datos del usuario en la página**: el nombre del negocio, los nombres de archivo y la escena propia se escriben
  siempre como texto (`textContent`), nunca como HTML. Los archivos se sirven solo por nombres que el servidor conoce
  (los que él mismo creó), nunca por rutas que lleguen en la petición.

## 2. Archivos

```
herramientas-ia/
├── AGENTS.md · CLAUDE.md · .gitignore
├── estilo/estilo.css      variables de color, base común y estilos de la firma
├── estilo/firma.html      la firma de Ismagit: el bloque que cada página lleva en su pie
├── inicio/index.html      lista de herramientas
├── modelos/               modelos de recorte (fuera de git)
└── estudio-fotos/
    ├── pyproject.toml · uv.lock · .python-version
    ├── plataformas.json   las 8 plataformas, editable
    ├── estudio/
    │   ├── __main__.py    arranque: puerto, servidor, espera, navegador
    │   ├── config.py      rutas y variables de entorno (incluidas las de pruebas, con su salvaguarda)
    │   ├── servidor.py    aplicación FastAPI: rutas, cabeceras de seguridad, estáticos, errores en español
    │   ├── estudio.py     el estudio: fotos, trabajos, cola y sesión en memoria
    │   ├── subidas.py     tipo por contenido, peso, píxeles, nombre limpio
    │   ├── recorte.py     recortadores (rembg y simulado), limpieza de máscara, «sin producto»
    │   ├── equipo.py      qué computador es, qué modelo toca, medición de la aceleración
    │   ├── prueba_aceleracion.py  subproceso que prueba un proveedor con tiempo máximo
    │   ├── plataformas.py lee y valida plataformas.json
    │   ├── encuadre.py    fondo blanco, porcentaje, regla de Amazon, JPEG y peso
    │   ├── clave.py       escribe y lee la línea de la clave en .env, máscara
    │   ├── ajustes.py     ajustes.json, colores y logo del negocio
    │   ├── openrouter.py  cliente httpx, errores por código, /key e /images
    │   ├── costos.py      modelos de escenas, estimación, tope de sesión, gastos.jsonl
    │   ├── escenas.py     texto de la petición, imagen de referencia, marca IPTC (XMP)
    │   ├── descargas.py   ZIP y resumen.csv
    │   └── registro.py    registros sin claves ni rutas personales
    ├── web/               index.html, app.css, app.js
    ├── pruebas/           pytest: rápidas, modelo real (-m modelo) y punta a punta (-m e2e)
    ├── trabajo/ · salidas/
    └── README.md · CAMBIOS.md · FICHA.md · PLAN.md · TAREAS.md · PRUEBAS.md · REVISION.md
```

## 3. API

| Método y ruta | Qué hace |
|---|---|
| `GET /` · `/web/*` · `/estilo/*` · `/marca/*` | la página y sus archivos, todos locales |
| `GET /api/estado` | el estado: fotos, trabajos, modelo de recorte, ajustes (clave enmascarada), gasto de la sesión |
| `GET /api/opciones` | plataformas, escenas preparadas, formatos, modelos de escenas y límites de subida |
| `POST /api/fotos` | sube hasta 20 fotos (multipart); responde foto a foto: aceptada, aviso o error |
| `DELETE /api/fotos/{id}` · `DELETE /api/fotos` | quita una foto de la lista o empieza de nuevo (no borra `salidas/`) |
| `POST /api/modelo/reintentar` | reintenta la descarga del modelo de recorte |
| `GET /api/fotos/{id}/vista` · `/recorte` | vista previa del antes y del después |
| `POST /api/medidas` | genera fondo blanco y medidas para las fotos y plataformas elegidas |
| `GET /api/archivos/{id}/{nombre}` | un archivo de resultados (solo nombres registrados por el servidor) |
| `GET /api/descargar?plataforma=…` | ZIP de todo o de una plataforma (solo ids conocidos), con `resumen.csv` |
| `PUT /api/ajustes` · `POST`/`DELETE /api/ajustes/logo` · `GET /api/logo` | marca, calidad del recorte, modelo de escenas y tope |
| `PUT`/`DELETE /api/ajustes/clave` · `POST /api/ajustes/clave/probar` | guarda, borra y prueba la clave |
| `POST /api/escenas/estimar` | costo estimado y si cabe en el tope de la sesión; no gasta ni llama a internet |
| `POST /api/escenas` | genera las escenas; exige `confirmado: true` y el costo que vio el usuario |

Lo que se desactiva de FastAPI: `/docs`, `/redoc` y `/openapi.json` (cargan librerías de internet y están en inglés).
Los errores 404, 405, 413 y 422 y los rechazos por `Host` u `Origin` responden en español con `{"error": "…"}`; el 422
no devuelve nunca lo que se envió (así una petición mal formada con la clave no la repite en la respuesta).

## 4. Dependencias (todas con la versión fijada en `pyproject.toml` y `uv.lock`, ya resuelto)

Python **3.12** (`.python-version`; `requires-python = ">=3.12,<3.14"`, porque numpy 2.5 ya no admite 3.11).

| Paquete | Versión | Para qué |
|---|---|---|
| fastapi | 0.162.6 | servidor |
| uvicorn | 0.54.0 | servidor |
| python-multipart | 0.0.33 | subida de fotos (lo pide FastAPI para multipart) |
| pillow | 13.0.0 | imágenes |
| numpy | 2.5.4 | máscaras y comprobaciones de píxeles |
| rembg | 2.0.87 | recorte; con el grupo `cpu` trae onnxruntime 1.32.0 |
| httpx | 0.28.1 | OpenRouter |
| pytest | 9.2.0 | pruebas (grupo `pruebas`) |
| playwright | 1.65.1 | pruebas de punta a punta con Chromium (grupo `pruebas`) |

**Tarjeta NVIDIA, como opción aparte**: `onnxruntime` y `onnxruntime-gpu` no pueden convivir, así que van en dos grupos
de uv declarados incompatibles: `cpu` (`rembg[cpu]`, el grupo por defecto) y `gpu` (`rembg[gpu]`). El comando normal
instala `cpu`. En un PC con NVIDIA el comando alternativo es
`uv run --directory estudio-fotos --no-default-groups --group gpu python -m estudio`. La tarjeta se da por presente si
onnxruntime ofrece `CUDAExecutionProvider`; si al crear la sesión CUDA no queda activo (faltan CUDA o cuDNN), la
herramienta sigue con el procesador y la página lo dice. Este camino queda sin probar en esta construcción (Mac).

## 5. Riesgos

| Riesgo | Qué hacemos |
|---|---|
| rembg sin nombre de modelo usa `bria-rmbg` (licencia no comercial); comprobado en el código de rembg 2.0.87 | una sola función crea la sesión y solo admite `birefnet-general` y `birefnet-general-lite`; una prueba recorre el código y falla si hay otro `new_session`, un `remove(` de rembg o `bria` fuera de esa defensa |
| La carpeta de modelos | comprobado en el código de rembg 2.0.87: `REMBG_HOME` es la raíz y cada modelo queda en `<REMBG_HOME>/models/<nombre>/<nombre>.onnx`; si existe `U2NET_HOME`, gana. Ponemos **las dos** variables apuntando a `herramientas-ia/modelos/` (también en el subproceso de aceleración), y la prueba con el modelo real comprueba que el archivo está ahí y que no aparece nada en la carpeta personal |
| CoreML falla o tarda minutos con BiRefNet | se prueba una sola vez, en un subproceso, con 2 minutos como máximo para preparar el modelo; si falla, se sigue con el procesador y el lote no se rompe |
| Descarga de 973 MB lenta o cortada | avance visible (tamaño en `modelos/`), mensaje de error con botón para reintentar; las fotos esperan en la cola y el resto de la página sigue respondiendo (prueba con un recortador de descarga lenta y otro que falla) |
| JPEG que deja el blanco en 254 | después de guardar se abre el archivo y se comprueba **todo** lo que queda fuera del producto (con 16 px de margen por la compresión); si no es 255, se baja la calidad de 1 en 1 (hasta 4 puntos; nunca sube) |
| Neblina de la máscara que mancha el blanco, o halo del fondo original | limpieza mínima y probada: solo se anula el alfa por debajo del 5 % y se estira el resto; no se erosiona nada. Se revisa además a ojo con las 5 muestras (control 1) y se anota en `PRUEBAS.md` |
| Fuga de la clave | la clave solo vive en `.env`; nunca en respuestas, errores ni registros; filtro que tapa patrones `sk-or-…`; el 422 no repite la entrada; pruebas que buscan la clave falsa (generada al ejecutar, no escrita en el código) en respuestas, registros, salidas y página |
| Una prueba que escriba el `.env` real | salvaguarda en `config.py`: las variables de prueba van juntas o la herramienta no arranca; un vigilante de pytest comprueba que el `.env` real, `ajustes.json`, `gastos.jsonl` y `salidas/` no cambian durante las pruebas |
| Otra web del navegador llamando al servidor local (y gastando) | se comprueban `Host` y `Origin`; las escenas exigen confirmación explícita; política CSP |
| El contrato de OpenRouter (`/images`, `/key`) no se puede probar de verdad sin gastar | se implementa tal como lo da la ficha; el simulador rechaza cualquier petición que no tenga exactamente esa forma; la primera escena real del usuario es la comprobación final (control 6) |
| Fotos enormes («bombas de descompresión») | tope de 50 megapíxeles, comprobado en la cabecera antes de decodificar |
| Rutas personales en los registros | los errores no controlados se registran sin traza de rutas; un filtro cambia la carpeta personal por `~` |
| Windows sin probar | rutas con `pathlib`, UTF-8 explícito, un solo comando con `uv run`; se anota en el README |

## 6. Decisiones

La ficha manda; donde no dice nada, elegimos lo más simple:

1. **Python 3.12**: la versión con más paquetes ya compilados para Mac y Windows dentro de las que admite rembg.
2. **Comando de arranque**: `uv run --directory estudio-fotos python -m estudio`, igual en Mac, Linux y Windows.
3. **Sesión en memoria**: una «sesión» es desde que arranca el servidor hasta que se cierra. El tope de gasto cuenta
   desde el arranque. Los resultados quedan en `salidas/<fecha_hora>/`.
4. **Subidas**: multipart en una sola petición (así el máximo de 20 se comprueba en el servidor); los temporales de la
   subida van a `trabajo/` (`tempfile.tempdir`), no a la carpeta temporal del sistema. El máximo de 25 MB se cuenta en
   MB binarios (25 × 1024 × 1024 bytes), para no rechazar una foto que el sistema muestra como «25 MB».
5. **Megapíxeles**: máximo 50 (cubre las cámaras de 48 y 50 MP); mensaje propio: «La foto mide N megapíxeles: el máximo
   es 50. Redúcela y vuelve a subirla.»
6. **Más de 20 fotos**: «Se pueden subir hasta 20 fotos a la vez.»
7. **Porcentaje en medidas no cuadradas** (Instagram 1080×1350): desviación anotada respecto a «el lado más largo»: el
   producto cabe entero en la caja porcentaje×ancho por porcentaje×alto (la regla literal dejaría sin margen lateral un
   producto casi cuadrado). En un lienzo cuadrado las dos reglas coinciden. El «porcentaje ocupado» de las pruebas y de
   `resumen.csv` se define igual: el mayor entre ancho del producto ÷ ancho y alto del producto ÷ alto.
8. **Peso**: 1 KB = 1000 bytes y 1 MB = 1000 KB, la lectura más estricta de cada máximo.
9. **Amazon**: lado del lienzo = ⌊lado más largo del producto ÷ 0,85⌋, acotado entre 1000 y 2000; cualquier ampliación
   lleva el aviso «ampliada ×N: Amazon pide no agrandar las fotos pequeñas».
10. **Orientación, color y metadatos**: se aplica la orientación EXIF y se convierte a sRGB al abrir; los JPEG llevan
    perfil sRGB y ningún otro metadato de la foto original (ni el GPS del teléfono).
11. **Nombres**: el nombre de la foto se limpia a letras sin acentos, números, `-` y `_`. Dos fotos con el mismo nombre
    en la sesión: la segunda es `nombre-2`. Los ids de plataforma para los nombres de archivo: `mercadolibre`, `amazon`,
    `shopify`, `tiendanube`, `instagram`, `catalogo-meta`, `whatsapp` y `google`.
12. **`plataformas.json`**: `id`, `nombre`, `ancho`, `alto`, `porcentaje`, `peso_maximo_kb` (o `null` si la plataforma
    no publica un máximo), `dice`, `fuente` y, para Amazon, `sin_ampliar`, `ancho_minimo` y `alto_minimo`. Si tiene un
    error, la página lo dice («plataformas.json tiene un error: …», sin rutas) y no genera medidas hasta corregirlo.
13. **Modelos de escenas** (tabla fija en `costos.py`, con prueba): `google/gemini-nano-banana-2.1` (recomendado y por
    defecto, 0,04 $), `google/gemini-3.1-flash-lite-image` (0,04 $), `google/gemini-3.1-flash-image` (0,07 $) y
    `google/gemini-3-pro-image` (0,14 $). Ajustes rechaza cualquier otro id. Tope por defecto: 1 $.
14. **`gastos.jsonl`**: una línea por cada imagen generada (`imagenes: 1`), escrita al momento: si algo se corta a mitad
    del lote, lo gastado ya está anotado. Las fallidas no escriben línea ni entran en la media. La estimación usa la
    media de `costo_usd ÷ imagenes` del mismo modelo; la página muestra la suma real del lote.
15. **Orden antes de gastar**: (1) al estimar no se llama a internet: solo cuenta el tope de la sesión; (2) al confirmar
    se vuelve a comprobar el tope local **primero** (si se supera, no se llama a OpenRouter); (3) después se consulta
    `/key`: si la estimación supera `limit_remaining`, no se gasta: «Esto costaría X $ y a tu clave de OpenRouter le
    quedan Y $. Sube el límite de la clave en OpenRouter o genera menos escenas.» Una clave sin límite (`limit` nulo)
    pasa; (4) el tope se vuelve a comprobar antes de cada imagen del lote.
16. **Escenas**: una escena por cada foto elegida. La imagen de referencia es el producto sobre blanco en 1024×1024,
    al 85 %, JPEG con calidad 90. La escena se guarda en JPEG con calidad 90 y la marca IPTC, **en la medida que
    devuelve el modelo**: no se amplía ni se deforma. Si la proporción no es exactamente la pedida, se recorta centrada
    lo mínimo para dejarla exacta (ese es el único «cambio de medida», y conserva la marca). El nombre:
    `<foto>_escena_<escena>_<ancho>x<alto>.jpg`. La escena «Fondo liso con los colores de tu marca» envía los dos
    colores de Ajustes. En la página, cada escena lleva la marca «Para redes y fotos secundarias».
17. **Texto fijo de la petición**: en español, igual que el resto; el usuario puede leer lo que se envía.
18. **Errores de OpenRouter**, por código y campos estructurados (`error.metadata.limit_source`, `error.metadata.reason`,
    `error.code`, `error.type`), nunca por el texto:
    - 401 → clave no válida; 400 → foto rechazada; 502 → generación fallida (no se reintenta sola); 503 → sin proveedor;
    - 402 sin más, o 402/403 con `openrouter_key_limit` u `openrouter_credits` → saldo o límite agotado;
    - 402 con `openrouter_in_flight_budget`: se espera `Retry-After` y se reintenta, salvo `reason` igual a
      `weight_exceeds_budget`, que da directamente el mensaje de saldo o límite agotado;
    - 403 con `content_policy_violation` en un campo estructurado → filtro de contenido; cualquier otro 403 → error
      genérico con el código;
    - 429 → se espera `Retry-After` (5 s si no viene; 60 s como máximo) con el mensaje de la ficha;
    - hasta 3 reintentos; si se agotan: «OpenRouter sigue pidiendo esperar. Prueba de nuevo en unos minutos.»;
    - otros códigos: «OpenRouter respondió con un error (código N). Inténtalo otra vez en unos minutos.»;
    - tiempo agotado: «OpenRouter no respondió a tiempo. Antes de repetir, mira en openrouter.ai si se cobró.»: el lote
      se detiene y la estimación de esa imagen cuenta como posible gasto para el tope de la sesión.
19. **Probar la clave**: `/key` puede venir con los datos dentro de `data` o sueltos; se aceptan las dos formas. Sin
    límite: «Conexión correcta · sin límite · usado 0,12 $».
20. **`resumen.csv`**: UTF-8 con BOM (para que Excel lea los acentos), separado por comas, solo con nombres de archivo
    (sin rutas). El README avisa de que un Excel configurado con `;` necesita «Datos › Desde texto».
21. **Medición de la aceleración**: una sola vez por modelo, en un subproceso con su carpeta temporal dentro de
    `trabajo/`, cuando termina el primer lote y no hay nada en la cola (el primer lote no espera: empieza con el
    procesador). El resultado se guarda en `medicion.json`.
22. **Sin producto**: si la máscara cubre menos del 5 % o más del 95 % de la foto (lo mismo que pide la prueba de la
    ficha para decir que un recorte «tiene un producto»).
23. **Solo para las pruebas**: `ESTUDIO_CARPETA_DATOS` (carpeta temporal para `.env`, `ajustes.json`, el logo,
    `gastos.jsonl`, `medicion.json`, `trabajo/` y `salidas/`), `ESTUDIO_OPENROUTER_URL` (solo se acepta si apunta a
    `127.0.0.1` o `localhost`), `ESTUDIO_RECORTADOR=simulado` y `ESTUDIO_PUERTO`. **Salvaguarda**: la carpeta de datos
    y el simulador van juntos; con una variable sin la otra, la herramienta no arranca. La carpeta temporal de pytest
    queda dentro de `estudio-fotos/.pruebas-tmp/`.
24. **Punta a punta**: con el modelo real (ya descargado) y OpenRouter simulado. Con las muestras, dos fotos llevan el
    aviso de menos de 1.000 px y los archivos de Amazon salen de 1000×1000 con aviso de ampliación: es lo esperado.
25. **Chromium de Playwright** se instala dentro de la carpeta (`estudio-fotos/.navegadores/`, fuera de git), no en la
    carpeta personal. La caché de paquetes de uv sí queda donde uv la tiene siempre.
26. **Grupo `pruebas`**: pytest y Playwright no se instalan al abrir la herramienta, solo al probarla
    (`uv run --group pruebas pytest`).
27. **Fuera de git**, además de lo que pide la ficha: `ajustes.json`, `medicion.json`, el logo del negocio,
    `.navegadores/` y `.pruebas-tmp/`.
28. **Protección local**, mínima: el servidor rechaza peticiones con otro `Host` u `Origin` (acepta `127.0.0.1` y
    `localhost`, y las peticiones sin `Origin`), y envía una política CSP que solo permite archivos propios.
29. **Puerto ocupado**: siempre el siguiente libre, y se dice (en la consola y en la página).
30. **La firma** es un bloque de HTML fijo (`estilo/firma.html`) que cada página lleva escrito en su pie, con el único
    enlace que da la ficha (`?origen=herramienta-estudio-fotos`).
31. **La clave** se guarda como `OPENROUTER_API_KEY=…` y se rechaza si tiene espacios, saltos de línea o menos de 8
    caracteres: «La clave no parece válida: cópiala entera, sin espacios.» Se puede borrar desde Ajustes.
32. **Logo del negocio**: pasa las mismas comprobaciones que una foto (tipo por contenido: JPG, PNG o WEBP, nunca SVG;
    hasta 5 MB; tope de píxeles), se vuelve a guardar como PNG de 600 px como máximo en `logo_negocio.png` y se puede
    quitar. Los colores solo se aceptan con la forma `#RRGGBB`.
33. **Recorte PNG**: del tamaño de la foto original, con transparencia.
34. **Rutas de más respecto a la ficha**, las mínimas para que la página se pueda usar, cada una con su prueba: quitar
    una foto, empezar de nuevo, borrar la clave, quitar el logo y reintentar la descarga del modelo.
35. **Cómo se mide la aceleración** (detalle de la decisión 21, escrito al construir el paso 18):
    - los 2 minutos cubren toda la prueba del acelerador: preparar el modelo con CoreML y recortar una foto. Es más
      estricto que la ficha (que los pide solo para preparar) y más simple: un solo reloj;
    - la foto de la prueba se dibuja en el propio proceso (1024×1024, el tamaño con el que trabaja el modelo): no se usa
      ni se copia ninguna foto del usuario. El tiempo del procesador es la mediana de lo que tardó el modelo en las
      fotos del primer lote;
    - se elige CoreML solo si su tiempo por foto es menor que el del procesador. Entonces el modelo se vuelve a
      preparar con CoreML al empezar el lote siguiente, nunca a mitad de un lote. Si CoreML falla al usarlo de verdad,
      el recortador vuelve al procesador en esa misma foto y queda anotado para no intentarlo más;
    - `medicion.json` guarda, por modelo: fecha, acelerador, segundos con el procesador, segundos con el acelerador,
      con cuál se queda y por qué. Sin rutas. Para volver a medir, se borra ese archivo;
    - el proceso de la prueba se corta a los 2 minutos, y también al cerrar la herramienta (una prueba cortada así no
      se guarda: se repite la próxima vez). Por si la herramienta desaparece sin cerrarse, el proceso se pone además su
      propio límite;
    - la página lo dice en Ajustes › Calidad del recorte: «Midiendo si la aceleración…» mientras dura, y después lo
      que salió;
    - con una tarjeta NVIDIA no hay prueba aparte: CUDA se usa si carga y, si no carga, se sigue con el procesador
      en el momento y la página lo dice (no hay minutos de preparación que acotar);
    - las pruebas automáticas no miden solas (`Config.medir` es falso en el modo de pruebas): usan procesos de mentira
      que fallan, tardan o ganan. La medición de verdad en este computador va con `pytest -m modelo`.
36. **Lo que se decidió al corregir la revisión de seguridad** (paso 21; el detalle está en `REVISION.md`):
    - **la consola**: todo lo que llega a ella pasa por el filtro de los registros, también lo que no escribe la
      herramienta: la descarga del modelo (pooch), los avisos de Python, los registros de las librerías y los errores
      no controlados. De esos errores se escribe el tipo y el archivo y la línea (sin su carpeta), nunca la traza;
    - **una subida «por trozos»** (`Transfer-Encoding`) se rechaza con el mismo 411 que una subida sin peso, en vez de
      contar los bytes al recibirla: es lo más simple y la página nunca sube así;
    - **sin contraseña local**: la herramienta solo escucha en `127.0.0.1` y rechaza lo que viene de otra web; un
      código de sesión complicaría abrirla. El README avisa de que conviene cerrarla en un computador compartido;
    - **una sola copia a la vez**: no se impide (el puerto siguiente sirve para cuando el 8601 lo ocupa otro
      programa); el README lo avisa;
    - **`trabajo/` se vacía también al cerrar**, para que las fotos subidas no se queden ahí;
    - **los temporales del acelerador**, si la medición lo elige, van a `trabajo/acelerador`. En este computador no se
      pudo comprobar con CoreML de verdad: aquí la medición deja el procesador.

## 7. Notas del Revisor sobre el plan

El Revisor (subagente con el contexto limpio) comparó la primera versión del plan con la ficha. Veredicto: «Hay que
corregir 12 puntos antes de construir». Lo que anotó y lo que se hizo:

| Nota del Revisor | Gravedad | Corrección |
|---|---|---|
| Nada garantiza que todas las pruebas usen la carpeta temporal y el simulador | alta | salvaguarda en `config.py` y vigilante en pytest (decisión 23, riesgo 8, pasos 2 y 12) |
| Faltan la tabla de modelos de escenas, el modelo por defecto y el tope de 1 $ | media | decisión 13 y paso 8 |
| Reglas de códigos de OpenRouter incompletas (`weight_exceeds_budget`, dónde se lee `content_policy_violation`, reintentos agotados, textos engañosos) | media | decisión 18 y paso 9 |
| `/docs`, `/redoc`, 422 que repite la entrada, errores en inglés | media | apartado 3 y paso 12 |
| Estados de la descarga del modelo sin prueba; el tamaño del modelo en el texto; la variable de la carpeta | media | riesgos 2 y 4, pasos 5 y 6 |
| Sin pasos para `PRUEBAS.md`, Revisión, Demo y Entrega | media | pasos 21 a 23 |
| Ninguna prueba exige la forma exacta de la petición a OpenRouter; falta la imagen de referencia | media | decisión 16 y paso 9 |
| Faltan «Para redes y fotos secundarias» y los colores de la marca en la escena 3 | media | decisión 16 y pasos 11 y 16 |
| Logo, colores, textos del usuario y nombres de archivo sin validación declarada | media | apartado 1, decisiones 12 y 32, pasos 8 y 12 |
| Reutilizar otra copia abierta contradice «usa el siguiente libre y dilo» | media | eliminado (decisión 29) |
| Se llamaba a `/key` antes de confirmar y antes del tope local | media | decisión 15 |
| Medidas fijas para las escenas: obligaban a ampliar o deformar | media | decisión 16: medida del modelo, sin ampliar ni deformar |
| Clave sin límite; cambio de `.env` sin reiniciar | baja | decisión 19 y paso 8 |
| Paso de la página demasiado grueso | baja | pasos 14 a 17, cada uno con su recorrido de punta a punta |
| Pruebas no explícitas (20 fotos, aviso de 1.000 px, sin clave, una sola sesión, navegador, código, documentos) | baja | pasos 3, 6, 9, 12, 13 y 20 |
| Camino NVIDIA sin describir | baja | apartado 4 |
| Rutas personales en trazas, mensajes y CSV | baja | riesgo 12, decisiones 12 y 20 |
| Ids de plataforma, nombres repetidos, esquema de `plataformas.json` | baja | decisiones 11 y 12 |
| Limpieza de máscara no pedida y sin prueba | baja | se mantiene mínima y con prueba (riesgo 6): sin ella la neblina del modelo mancha el blanco puro |
| El remedio del blanco no puede subir la calidad; hay que comprobar todo el fondo | baja | riesgo 5 |
| «Sin producto» al 1 % y 99 % no coincide con la prueba de la ficha | baja | decisión 22 |
| Enlace inventado para la página de inicio; la firma por JavaScript no se ve en el HTML | baja | decisión 30 |
| Rutas que la ficha no pide | baja | decisión 34: quedan las mínimas, con prueba; se quitó «reintentar una foto» |
| Dudas: 100 megapíxeles, CSV, punta a punta con modelo real, prueba real temprana, carpeta temporal de pytest, clave falsa generada | — | decisiones 5, 20, 23 y 24; pasos 5 y 12 |

## 8. Versión 1.1 · plan corto

La ficha pasó a la versión 1.1 (`FICHA.md` es su copia). En `CAMBIOS.md` la última versión era la 1, así que no se
construye de nuevo: se pasa a la 1.1 con el mismo método (punto 13 de la ficha). Los apartados 1 a 7 son el plan de la
versión 1 y se quedan como estaban; aquí va solo lo que cambia. Segunda versión de este plan corto: incluye las
correcciones del Revisor (apartado 8.5).

### 8.1 Qué cambia

| Cambio (punto 13) | Qué se hace | Dónde |
|---|---|---|
| 1 · Diseño de Ismagit (punto 4.7) | las 11 variables de la ficha en `:root`, las fuentes Geist y Geist Mono locales, el logo arriba a la izquierda (28 px) con «Estudio de fotos» al lado, botones, tarjetas, campos, foco, estados, fondo real de cada foto y pantalla estrecha; se revisan Fotos, Resultados, Ajustes y los mensajes | `estilo/estilo.css`, `estilo/fuentes/`, `estilo/firma.html`, `web/index.html`, `web/app.css`, `web/app.js`, `inicio/` |
| 2 · Sin marca del negocio | fuera el nombre, los dos colores y el logo: de la página, del servidor (rutas del logo), del estado y de `ajustes.json`; la página ya no cambia de colores | `estudio/ajustes.py`, `config.py`, `estudio.py`, `servidor.py`, `web/` |
| 3 · Escenas | «Fondo liso con los colores de tu marca» pasa a ser «Fondo liso de un color», con un selector de color (por defecto, gris claro) | `estudio/escenas.py`, `estudio.py`, `servidor.py`, `web/` |
| 4 · Muestras | las pruebas usan todas las fotos de `muestras/`, sin un número fijo | `pruebas/` |
| 5 · Para Mac y Windows | el README dice que funciona en Mac y Windows, sin «aún sin probar» | `README.md` |
| 6 · Versión | `CAMBIOS.md` con la 1.1; `AGENTS.md`, `inicio/index.html` y la herramienta dicen 1.1 | documentos, `estudio/__init__.py`, `pyproject.toml` |

Además, lo que la ficha 1.1 cambia fuera del punto 13 y también se aplica: la nota de las escenas dice «Mercado Libre y
Amazon piden fondo blanco en la foto principal» (ya sin Google); el README cuenta para qué productos sirve, con sus dos
avisos (no es para fotos de personas; lo más difícil son los objetos transparentes); y «Carpetas comunes» de
`AGENTS.md` dice lo mismo que el árbol del punto 3 de la ficha.

Lo que el plan de la versión 1 decía y ya no vale: en el apartado 1, «el nombre del negocio» como dato del usuario; en
el 2, `ajustes.py` ya no lleva colores ni logo; en el 3, las rutas `POST`/`DELETE /api/ajustes/logo` y `GET /api/logo`
desaparecen; el riesgo de la neblina (ya no son «las 5 muestras»: son las que haya); las decisiones 27 y 32 (el logo
del negocio) y la parte del logo de la 23 y la 34; en la 16, la escena de los colores de la marca; y la 24 (con las
muestras de la guía 1.1, las fotos con el aviso de menos de 1.000 px son las que midan menos, no «dos»).

### 8.2 Archivos

- **Nuevos**: `estilo/fuentes/` (las 4 fuentes `.woff2` y `OFL.txt`, copiadas de `marca/fuentes/`),
  `pruebas/test_diseno.py`.
- **Cambian**: los de la tabla, las pruebas que nombraban la marca del negocio o contaban 5 muestras, y los documentos.
- **Se borran, porque lo pide el dueño de la carpeta** (la regla «no borres lo que ya existe» sigue valiendo para todo
  lo demás): las tres fotos de muestra y el logo de ejemplo de la versión 1, que ya no están en la guía 1.1. Se borran
  por su nombre exacto, sin comodines (una de las fotos que se quedan empieza igual que dos de las que se van), y se
  comprueba con `git status` que salen 4 borrados: 3 en el paso 24 y 1 en el 26. Quedan las 6 fotos de la guía 1.1 y,
  en `marca/`, los logos de Ismagit y `fuentes/`.
- **Entran en git** los archivos de la guía 1.1 que hoy solo están en la carpeta, cada uno en el primer commit que lo
  usa: la ficha en el paso 23, las 4 fotos nuevas en el 24, y `marca/ismagit_logo.png` y `marca/fuentes/` en el 28.
- **Sin dependencias nuevas**: no cambia ninguna versión; en `uv.lock` solo cambia la versión del proyecto.

### 8.3 Decisiones de la versión 1.1

Donde la ficha no dice nada, lo más simple:

1. **Variables**: en `:root` quedan las 11 de la ficha con sus valores exactos, y solo se añaden medidas (los radios)
   y las dos familias de fuentes. Las variables de la versión 1 desaparecen de todos los archivos. La prueba no es una
   lista de nombres prohibidos: toda variable que usan las tres hojas de estilo está definida en `:root` (salvo
   `--corte`, la del deslizador de cada foto), y cada una de las 11 de la ficha se usa al menos una vez.
2. **Fuentes**: se copian a `estilo/fuentes/` (copias idénticas, byte a byte, a las de `marca/fuentes/`) y
   `estilo.css` las declara con la regla `font-face` y una ruta relativa (`fuentes/…`): así sirven igual a la
   herramienta (`/estilo/…`) y a la página de inicio, que se abre como archivo. Cada familia tiene dos archivos
   (latino y latino ampliado), cada uno con su `unicode-range`, y peso de 100 a 900. Detrás van las fuentes del
   sistema, por si un navegador no carga una fuente local en una página abierta como archivo: la página se sigue
   leyendo (en Chromium, comprobado: las carga). Geist Mono va en cifras, medidas y nombres de archivo.
   Las pruebas que hoy prohíben la regla `font-face` y cualquier `url(` no se borran: pasan a ser una lista blanca
   igual de estricta. `font-face` solo en `estilo/estilo.css`; cada `url(` es `fuentes/<archivo>.woff2`, sin `//`,
   `:`, `..` ni `data:`, y el archivo existe; `web/app.css` e `inicio/inicio.css` siguen sin `url(` ni importaciones.
   `OFL.txt` trae dos direcciones escritas como texto: no son cargas y la prueba no las cuenta.
3. **Logo**: `marca/ismagit_logo.png` (el de la guía 1.1, pensado para fondo oscuro) en la cabecera (28 px de alto),
   en la firma (18 px) y como icono de la pestaña. Los otros dos logos de Ismagit se quedan en `marca/` (el dueño no
   pidió borrarlos), pero ninguna página los usa ya y ninguna prueba exige que existan. Se le pregunta en la entrega
   si los quiere fuera.
4. **Un solo botón principal por zona**, y las zonas son las tres de la ficha: en Fotos, «Generar medidas»; en
   Resultados, «Descargar todo (ZIP)»; en Ajustes, «Guardar ajustes». Los demás son secundarios (transparentes, con
   borde `--linea`), también «Ver el costo», «Guardar clave» y «Sí, generar»: la ficha define solo dos tipos de botón,
   y lo que destaca al confirmar un gasto es la caja de confirmación, con su borde en el acento. Se cuenta en el HTML
   y también en el navegador, con los resultados ya pintados (el de Resultados lo crea el código).
5. **El fondo real de cada foto**: los recortes, sobre cuadros claros; las fotos con fondo blanco, sobre blanco (también
   en los huecos que deja una medida no cuadrada); las escenas, sobre `--card2`. Siempre dentro de su tarjeta oscura.
6. **Avisos y errores sobre fondo oscuro**: el texto en `--aviso` o `--error` (o `--acento` cuando algo salió bien),
   sobre `--card2` y con el borde del mismo color. Una prueba calcula el contraste de cada pareja de texto y fondo con
   los valores de las variables y exige el nivel AA (4,5 a 1), y otra comprueba que las hojas solo usan esas parejas.
7. **Sin marca del negocio**: `PUT /api/ajustes` ya solo conoce la calidad del recorte, el modelo de escenas y el tope;
   un campo que no conoce (por ejemplo `negocio`, de una página antigua) no da error y no se guarda en ningún sitio.
   Las tres rutas del logo dejan de existir (responden 404 o 405). La comprobación de la subida «por trozos» (la
   corrección S1 de la revisión de la versión 1) se conserva para `/api/fotos`.
8. **Limpieza de lo que dejó la versión 1** (paso propio, el 27, con sus pruebas): al arrancar, si `ajustes.json` se
   lee bien y trae campos de más (los de marca), se vuelve a escribir solo con la calidad del recorte, el modelo de
   escenas y el tope, que quedan idénticos; si está roto o ya está limpio, no se toca. Y se borra
   `logo_negocio.png`, que era una copia reducida hecha por la propia herramienta: el logo original de quien la usa
   no se toca. La ruta de ese archivo sale siempre de la configuración (`Config.logo_antiguo`, dentro de la carpeta
   de datos), nunca de una ruta fija: en las pruebas es la carpeta temporal. Si algo no se puede borrar o escribir, la
   herramienta arranca igual. Nada de esto escribe en la consola el nombre del negocio ni rutas. El vigilante de las
   pruebas sigue mirando los archivos reales.
9. **«Fondo liso de un color»**: el id de la escena pasa a ser `fondo-liso` (así se llaman sus archivos:
   `<foto>_escena_fondo-liso_<ancho>x<alto>.jpg`). El color llega en el campo `color` de las dos rutas de escenas y se
   valida siempre en el servidor, con cualquier escena: solo vale un texto con la forma exacta `#RRGGBB`; otra cosa
   (otro tipo, vacío, mal formado) da un 400 con un mensaje fijo, que no repite lo enviado. Si no llega (o es nulo),
   es gris claro (`#D9D9D9`). El color solo entra en el texto de la petición de `fondo-liso`; nunca en los registros
   ni en `gastos.jsonl`. En Resultados, el título de esa escena lleva el código ya validado: «Fondo liso de un color
   (#D9D9D9)». En la página, el selector de color solo se ve con esa escena, con su código al lado; cambiar el color
   borra la estimación, como cualquier otro cambio del pedido.
10. **Muestras**: una sola función en `pruebas/conftest.py` da «todas las fotos de `muestras/`» (JPG, PNG y WEBP,
    ordenadas) y la usan todas las pruebas que las necesitan, que calculan con ellas lo que esperan (cuántas llevan
    el aviso de menos de 1.000 px, cuántos archivos trae el ZIP). Con menos de 3 fotos (las que piden los recorridos)
    o más de 20 (el máximo de una subida), la prueba lo dice.
11. **El frasco de vidrio** es transparente, lo más difícil según la ficha. La ficha pide para cada recorte que la
    máscara ocupe entre el 5 % y el 95 %; las pruebas de la versión 1 pedían además poca zona medio transparente
    (menos del 3 %). Si el frasco falla solo en eso que la ficha no pide, ese extra se relaja para todas las fotos y
    se anota en `PRUEBAS.md`. Nunca se saca una foto de la prueba.
12. **Versión**: `1.1` en la herramienta y en los documentos; `1.1.0` en `pyproject.toml`.
13. **Documentos**: `PRUEBAS.md` se actualiza sin vaciarlo: son nuevos el resumen, el tiempo por foto y los
    recorridos; se conservan la medición de la aceleración (medida otra vez, con su fecha), los seis controles y lo
    que no se probó. `REVISION.md` conserva la revisión de la versión 1 y añade la de la 1.1. La entrada de la
    versión 1 de `CAMBIOS.md` no se toca (es historia), y la de la 1.1 arrastra sus tres pendientes. En ningún
    documento, prueba ni archivo de código queda el negocio de ejemplo de la versión 1, tampoco sus colores; la prueba
    que lo comprueba arma el nombre por trozos para no llevarlo escrito. Dos de las fotos que se quedan en
    `muestras/` enseñan ese nombre en el producto: son de la guía 1.1 y se quedan. El historial de git no se reescribe.
14. **Para Mac y Windows**: el README lo dice como la ficha. `PRUEBAS.md` sigue contando lo que se probó de verdad en
    este computador, que es un Mac.
15. **La página de inicio** lleva el mismo diseño: el logo arriba a la izquierda, la tarjeta de la herramienta con su
    botón principal y la firma.
16. **Pantalla estrecha**: la cabecera, las filas de botones y los campos saltan de línea; el recorrido de diseño
    abre la página a 360 px de ancho y comprueba que no hay desplazamiento horizontal.
17. **Un navegador con la página de la versión 1 guardada**: los archivos de `/web/` y `/estilo/` salen con
    `Cache-Control: no-cache` (el navegador pregunta siempre si cambiaron): así nadie se queda con el código antiguo
    de la página leyendo un estado que ya no trae la marca.
18. **El recorrido de diseño** va antes del último recorrido (el que comprueba que ninguna petición salió de este
    computador y que la consola quedó limpia) y deja la ventana como estaba. Fuerza y captura los estados y los
    mensajes: vacío, un error (un archivo que no es una foto), un aviso (menos de 1.000 px), un «listo», la caja de
    confirmación y el error del tope; de cada uno mira el color del texto y el del fondo ya calculados. Las capturas
    van a `.pruebas-tmp/`, fuera de git.

### 8.4 Riesgos de la versión 1.1

| Riesgo | Qué hacemos |
|---|---|
| Las fuentes rompen la regla de «nada de internet» | lista blanca (decisión 2) en los archivos; y el recorrido de diseño comprueba en el navegador que Geist y Geist Mono quedan cargadas, ninguna con error, y que cada petición de fuente responde 200 desde este computador |
| La política de la página (CSP) no deja cargar las fuentes | `font-src 'self'` ya estaba; lo comprueba el mismo recorrido |
| Al pasar a fondo oscuro, algún texto queda sin leerse (oscuro sobre oscuro) en una pantalla o un mensaje | toda variable usada existe (decisión 1); el contraste se calcula (decisión 6); el recorrido de diseño mira los colores ya calculados por el navegador en cada estado y cada mensaje (decisión 18); y se revisan a ojo las capturas de Fotos, Resultados, Ajustes y los mensajes |
| La limpieza al arrancar borra o estropea algo de quien usa la herramienta | solo toca dos archivos que escribía la propia herramienta, con la ruta sacada de la configuración; conserva los otros tres ajustes idénticos; no toca un archivo roto; tiene su paso y sus pruebas (decisión 8), y queda dicho en `CAMBIOS.md` |
| El campo `color` llega del navegador y acaba en un texto que se envía a OpenRouter | forma exacta `#RRGGBB` o nada (decisión 9); la prueba de privacidad envía la clave falsa como color a las dos rutas y comprueba el 400 sin repetirla |
| El frasco de vidrio (transparente) se recorta mal | decisión 11; lo que salga se anota en `PRUEBAS.md` |
| Una prueba que dependa de fotos que ya no están | decisión 10 |
| Se borra un archivo de más | borrado por nombre exacto y `git status` (apartado 8.2) |

### 8.5 Notas del Revisor sobre el plan de la 1.1

El Revisor (subagente con el contexto limpio, que no escribe archivos) comparó la primera versión de este plan corto
con la ficha 1.1 y con el código de la versión 1. Veredicto: «Hay que corregir 10 puntos antes de construir» (1 de
gravedad alta y 9 de gravedad media), más 11 notas bajas. Lo que anotó y lo que se hizo:

| Nota del Revisor | Gravedad | Corrección |
|---|---|---|
| La limpieza al arrancar es el único código nuevo que borra y reescribe archivos reales, y no tenía paso propio, ni prueba del borrado del logo, ni decía de dónde sale la ruta | alta | decisión 8 y paso 27 propio, con sus pruebas (carpeta de la versión 1 completa, segunda arrancada sin cambios, archivo roto) |
| El paso 23 deja una prueba rápida en rojo: la guía 1.1 ya dejó sus fotos en `muestras/` y una prueba contaba 5 | media | anotado en el paso 23; el paso 24 la arregla |
| El paso del diseño era demasiado grueso | media | partido en tres: pasos 28, 29 y 30 |
| Las pruebas que prohibían `font-face` y `url(` podían borrarse sin más | media | lista blanca igual de estricta (decisión 2 y riesgo 1) |
| El campo `color`: la prueba de privacidad de los colores desaparecía con la marca; faltaba decir qué pasa con otra escena, vacío u otro tipo | media | decisión 9, riesgo 5 y paso 25 |
| El paso 26 no nombraba todas las pruebas de la marca, ni qué pasa con la corrección S1 | media | decisión 7 y paso 26, con la lista |
| El paso de documentos podía dejarse «Carpetas comunes» de `AGENTS.md`, la nota de Google del README y otras líneas | media | apartado 8.1 y paso 31, con sus pruebas |
| Al frasco de vidrio las pruebas le pedían más que la ficha | media | decisión 11 |
| «`PRUEBAS.md` se vuelve a escribir» podía perder la aceleración, los seis controles y lo no probado; los pendientes de `CAMBIOS.md` | media | decisión 13 y pasos 31 y 32 |
| El recorrido de diseño no obligaba a que aparecieran los mensajes | media | decisión 18 y paso 30 |
| Números fijos de muestras en muchas pruebas; seis sitios buscaban solo `*.jpg` | baja | decisión 10 y paso 24 |
| «Sí, generar» con borde de acento era un tercer tipo de botón | baja | decisión 4: secundario normal |
| El botón principal de Resultados lo crea el código: en el HTML no se ve | baja | decisión 4: se cuenta también en el navegador |
| Mejor que una lista de variables prohibidas: toda variable usada existe y las 11 se usan | baja | decisión 1 |
| El recorrido de diseño, antes del último; pasar la batería de punta a punta en los pasos que tocan la página | baja | decisión 18 y pasos 24 a 30 |
| Los otros dos logos de Ismagit: conservarlos, sin pruebas que los exijan, y preguntar al dueño | baja | decisión 3 |
| Borrar por nombre exacto; los archivos de la guía que aún no están en git | baja | apartado 8.2 |
| El paso final no nombraba la línea de cierre; la revisión corta no decía qué puntos | baja | pasos 33 y 34 |
| Rastros del negocio de ejemplo que una búsqueda del nombre no ve: sus colores en las pruebas; dos fotos que se quedan lo enseñan | baja | decisión 13 |
| Los documentos no pueden llevar el carácter de las direcciones de correo: `font-face` se escribe sin él | baja | así se escribe en todos |
| Un navegador con la página de la versión 1 guardada se rompería con el estado nuevo | baja | decisión 17 y paso 26 |

Lo que el Revisor dio por bueno aunque era fácil dudar: conservar los otros dos logos; cambiar el id de la escena (el
antiguo llevaba «marca» en el nombre de cada archivo); no dar error con un `negocio` desconocido; las fuentes del
sistema como respaldo (no son de internet); el README «Para Mac y Windows» con `PRUEBAS.md` diciendo lo que se probó; y
el orden de los pasos, que no deja pruebas rotas entre uno y otro.
