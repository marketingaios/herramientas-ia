# Plan · Estudio de fotos de producto · versión 1

Plan del Constructor para la ficha 1 (`FICHA.md`). Computador de construcción: Mac con chip Apple (arm64), uv 0.11.8,
git 2.50.1. Segunda versión del plan: incluye las correcciones del Revisor (apartado 7).

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
