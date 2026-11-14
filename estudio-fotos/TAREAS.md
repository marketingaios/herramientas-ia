# Tareas · Estudio de fotos · versión 1

Un paso a la vez. Cada paso tiene su prueba; las anteriores deben seguir pasando. Al terminar: casilla marcada y un
commit.

- Pruebas rápidas: `uv run --group pruebas pytest` (dentro de `estudio-fotos/`).
- Con el modelo real: `uv run --group pruebas pytest -m modelo`.
- De punta a punta: `uv run --group pruebas pytest -m e2e`.

## Construcción

- [x] **Paso 1 · Carpeta común y proyecto**: `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `estilo/` (CSS y firma),
      `inicio/`, `modelos/`; proyecto uv con las versiones fijadas y `uv.lock`.
      Prueba: `test_estructura.py` (los archivos existen; `CLAUDE.md` es `@AGENTS.md`; `AGENTS.md` tiene las reglas, el
      método, la tabla con sus columnas y el «Abre …»; `.gitignore` cubre lo pedido; todas las dependencias llevan
      `==`; la firma está en `inicio/index.html`).
- [x] **Paso 2 · Configuración y plataformas**: `config.py` con la salvaguarda de las pruebas, `plataformas.py`,
      `plataformas.json`.
      Prueba: `test_config.py` (carpeta temporal y simulador van juntos o no arranca; el simulador solo en
      `127.0.0.1`), `test_plataformas.py` (las 8 plataformas con los valores de la ficha; un JSON roto da un error
      claro y sin rutas).
- [x] **Paso 3 · Subidas**: tipo por contenido, HEIC, peso, lado corto, megapíxeles, foto dañada, nombre limpio.
      Prueba: `test_subidas.py` (cada mensaje del punto 5; el aviso por debajo de 1.000 px; nombres con rutas).
- [x] **Paso 4 · Fondo blanco y encuadre**: blanco 255, centrado, porcentaje, medida, JPEG sRGB, peso, regla de Amazon,
      aviso de ampliación, nombres de archivo.
      Prueba: `test_encuadre.py` (porcentaje ±1 %, centro ±1 %, medida y peso de cada plataforma, todo el fondo en 255).
- [x] **Paso 5 · Recorte**: recortador con rembg y BiRefNet (nombre siempre explícito), recortador simulado, limpieza
      mínima de máscara, «sin producto», modelo según el computador.
      Prueba: `test_recorte.py` (simulado; elección del modelo; la limpieza no muerde; nunca `bria-rmbg`) y, con el
      modelo real, `test_modelo_real.py` (`-m modelo`: las 5 muestras, máscara entre el 5 % y el 95 %, el modelo queda
      en `modelos/`, tiempo por foto).
- [x] **Paso 6 · El estudio y la cola de recorte**: fotos, nombres repetidos, avance «3 de 5 · foto_3.jpg · 4,2 s», una
      sola sesión por lote, un error no rompe el lote, estados de la descarga del modelo (descargando con su tamaño,
      fallida, reintento).
      Prueba: `test_cola.py`.
- [x] **Paso 7 · Medidas en lote, resultados y descarga**: medidas por foto y plataforma, ZIP de todo o de una
      plataforma, `resumen.csv`.
      Prueba: `test_medidas.py` (el lote de medidas y la descarga).
- [x] **Paso 8 · Clave y ajustes**: `.env` (solo su línea, permisos 600, se lee cada vez), máscara, `ajustes.json`,
      colores `#RRGGBB`, logo validado, calidad del recorte, modelos de escenas y tope de 1 $.
      Prueba: `test_clave.py`, `test_ajustes.py` (con un logo de ejemplo).
- [x] **Paso 9 · OpenRouter**: cliente, simulador con el contrato exacto de la ficha, `/key`, errores por código y
      campos estructurados, reintentos.
      Prueba: `test_openrouter.py` (éxito; forma exacta de la petición; sin clave; 401; 402; 403 con
      `openrouter_key_limit` y con `openrouter_credits`; 402 en vuelo, con y sin `weight_exceeds_budget`; 403 con
      `content_policy_violation`; otro 403; 429 y reintentos agotados; 502; 503; 400; sin conexión; un texto de error
      engañoso no cambia el mensaje).
- [x] **Paso 10 · Costos**: modelos y costo de partida, estimación con la media real, tope de la sesión,
      `gastos.jsonl`.
      Prueba: `test_costos.py` (estimación correcta; con el tope superado no se llama a OpenRouter; lo que queda en la
      clave; formato de los importes).
- [x] **Paso 11 · Escenas**: texto fijo, las 5 escenas y la propia, colores de la marca, imagen de referencia, formato
      exacto sin ampliar ni deformar, marca IPTC, lote con costo real.
      Prueba: `test_escenas.py` (la marca IPTC está y se conserva al cambiar de medida).
- [x] **Paso 12 · Servidor**: rutas de la API, estáticos, `Host`/`Origin`, CSP, errores en español, sin `/docs`.
      Prueba: `test_servidor.py` (incluye más de 20 fotos y cada ruta de más), `test_privacidad.py` (ninguna respuesta,
      registro, salida ni página contiene la clave falsa; el 422 no repite la entrada; sin rutas personales),
      `test_codigo.py` (sin `shell=True`, `eval` ni `exec`; las únicas direcciones de internet del código son
      openrouter.ai; el vigilante de los archivos reales).
- [x] **Paso 13 · Arranque**: `python -m estudio`: puerto libre, solo `127.0.0.1`, espera, dirección,
      `NO_ABRIR_NAVEGADOR=1`.
      Prueba: `test_arranque.py` (elige el siguiente puerto libre y lo dice; el proceso responde y escribe la
      dirección; no escucha en otras interfaces; con `NO_ABRIR_NAVEGADOR=1` no abre el navegador).
- [x] **Paso 14 · Página · Fotos**: subir y arrastrar, errores por archivo, avisos «Calidad máxima» y «Modo rápido…»,
      descarga del modelo, barra de avance, deslizador antes/después sobre fondo de cuadros, firma en el pie.
      Prueba: `test_pagina.py` (nada de internet salvo el enlace de la firma) y recorrido 1 de `test_e2e.py`.
- [x] **Paso 15 · Página · Medidas y Resultados**: selector de plataformas, generar, cuadrícula por foto, avisos por
      archivo, descarga de todo o por plataforma.
      Prueba: recorrido 2 de `test_e2e.py` (Mercado Libre, Amazon e Instagram; ZIP comprobado).
- [x] **Paso 16 · Página · Ajustes**: clave (••••, Probar, borrar), marca del negocio, calidad del recorte, modelo de
      escenas y tope.
      Prueba: recorrido 3 de `test_e2e.py`.
- [x] **Paso 17 · Página · Escenas**: elegir fotos, escena y formato; costo estimado; confirmar; avance; costo real;
      «Para redes y fotos secundarias».
      Prueba: recorrido 4 de `test_e2e.py` (2 escenas con OpenRouter simulado).
- [x] **Paso 18 · Aceleración medida**: prueba de CoreML en un subproceso con 2 minutos como máximo, `medicion.json`,
      se queda con lo más rápido.
      Prueba: `test_aceleracion.py` (falla → procesador; tarda demasiado → procesador; más rápida → se elige) y la
      medición real en este computador.
- [x] **Paso 19 · Documentos**: `README.md`, `CAMBIOS.md`, tabla de `AGENTS.md`, `inicio/index.html`.
      Prueba: `test_estructura.py` ampliada (el comando de arranque aparece en `AGENTS.md` y en el `README.md`).

## Pruebas, revisión y entrega

- [x] **Paso 20 · Pruebas**: todas (rápidas, modelo real y punta a punta) → `PRUEBAS.md` con cuántas pasan, cuánto
      tardan, el tiempo por foto y la medición de la aceleración.
- [x] **Paso 21 · Revisión**: el Revisor comprueba los 10 puntos de seguridad y escribe `REVISION.md`; se corrige, se
      vuelven a pasar las pruebas y el Revisor comprueba lo corregido.
- [x] **Paso 22 · Demo y entrega**: arrancar la herramienta, dar la dirección y el resumen final.

# Tareas · versión 1.1

El paso a la versión 1.1 (ficha 1.1, punto 13; plan corto en el apartado 8 de `PLAN.md`). Igual que antes: un paso a
la vez, cada uno con su prueba y su commit, y las pruebas anteriores siguen pasando. En los pasos que tocan la página
(24 a 30) se pasa también la batería de punta a punta entera; en el 24, además, la del modelo real.

## Plan

- [x] **Paso 23 · Ficha 1.1 y plan corto**: `FICHA.md` es la copia de la ficha 1.1; apartado 8 de `PLAN.md` y estos
      pasos; el Revisor compara el plan con la ficha y se corrige lo que anota (apartado 8.5).
      Prueba: `test_estructura.py` (la ficha guardada es la ficha). En la carpeta queda en rojo una prueba rápida
      hasta el paso 24: la guía 1.1 ya dejó sus fotos en `muestras/` y `test_servidor.py` contaba 5.

## Construcción

- [x] **Paso 24 · Muestras**: una función de `conftest.py` da todas las fotos de `muestras/` y la usan todas las
      pruebas, sin un número fijo; entran en git las 4 fotos nuevas de la guía y salen, por su nombre exacto, las 3 de
      la versión 1.
      Prueba: `test_servidor.py` (todas las muestras pasan por el servidor; el aviso de menos de 1.000 px, contado con
      las propias fotos), `test_modelo_real.py` (cada recorte tiene un producto) y los recorridos de `test_e2e.py`,
      que cuentan las fotos que hay.
- [x] **Paso 25 · Escenas · «Fondo liso de un color»**: el id `fondo-liso`, el campo `color` (`#RRGGBB`, validado
      siempre; gris claro si no llega) en las dos rutas de escenas, el selector de color en la página y la nota sin
      Google.
      Prueba: `test_escenas.py` (el color va en el texto de la petición y solo en esa escena; uno que no vale se
      rechaza con su mensaje, con cualquier escena; por defecto, gris claro; el nombre del archivo y el título),
      `test_servidor.py` (el campo `color` por HTTP; la nota de las escenas en `/api/opciones`), `test_privacidad.py`
      (la clave falsa enviada como color a las dos rutas: 400 sin repetirla) y el recorrido 4 de `test_e2e.py` (el
      selector solo se ve con esa escena).
- [x] **Paso 26 · Sin marca del negocio**: fuera el nombre, los colores y el logo de `ajustes.py`, `estudio.py`,
      `servidor.py` (las tres rutas del logo) y de la página; fuera el logo de ejemplo de `marca/`; `/web/` y
      `/estilo/` con `Cache-Control: no-cache`.
      Prueba: `test_ajustes.py` (solo quedan la calidad, el modelo y el tope; un `negocio` enviado no se guarda),
      `test_servidor.py` (las rutas del logo responden 404 o 405; el estado no lleva `negocio`; la subida «por trozos»
      se sigue rechazando en `/api/fotos`; la cabecera de caché), `test_privacidad.py` y `test_clave.py` (un `negocio`
      con la clave falsa no deja la clave en ninguna respuesta ni archivo), `test_pagina.py` (la página no tiene
      campos de marca), `test_escenas.py` y `test_codigo.py` (sin restos de la marca; el vigilante sigue mirando
      `logo_negocio.png`) y el recorrido 3 de `test_e2e.py`.
- [x] **Paso 27 · Limpieza de lo que dejó la versión 1**: al arrancar, `ajustes.json` sin los campos de marca (la
      calidad, el modelo y el tope quedan idénticos) y `logo_negocio.png` borrado; la ruta sale de la configuración
      (`Config.logo_antiguo`).
      Prueba: `test_ajustes.py` (una carpeta de la versión 1 completa queda limpia y conserva los tres ajustes; una
      segunda arrancada no cambia nada; un `ajustes.json` roto no se toca y no impide arrancar; si el logo no se
      puede borrar, arranca igual; nada sale por la consola) y `test_config.py` (en pruebas, esa ruta está en la
      carpeta temporal).
- [x] **Paso 28 · Diseño (1) · variables, fuentes, firma e inicio**: `estilo/estilo.css` con las 11 variables, las
      fuentes Geist locales (`estilo/fuentes/`, con su licencia) y los estilos comunes (botones, tarjetas, campos,
      foco, avisos, barra, firma); `app.css` pasa a las variables nuevas; la firma y la página de inicio, con el logo
      de la guía 1.1, que entra en git con `marca/fuentes/`.
      Prueba: `test_diseno.py` (los valores de la tabla; toda variable usada existe y las 11 se usan; las fuentes son
      copias idénticas y solo se cargan de la carpeta; contraste AA calculado; botones, tarjetas, campos y foco como
      en la ficha), `test_pagina.py` (la lista blanca: nada de internet, tampoco las fuentes) y `test_estructura.py`
      (la firma).
- [x] **Paso 29 · Diseño (2) · la página**: la cabecera con el logo de Ismagit (28 px) y «Estudio de fotos», las tres
      zonas, un solo botón principal por zona, Geist Mono en cifras, medidas y nombres de archivo, tarjetas y campos.
      Prueba: `test_diseno.py` (el logo y el nombre; un solo principal por zona en el HTML; Geist Mono donde toca) y
      `test_pagina.py`.
- [x] **Paso 30 · Diseño (3) · fotos, mensajes y pantalla estrecha**: el fondo real de cada foto (cuadros claros,
      blanco, `--card2`), los avisos y errores, 360 px de ancho; se revisan Fotos, Resultados, Ajustes y los mensajes
      con capturas.
      Prueba: `test_diseno.py` (el fondo de cada foto) y el recorrido de diseño de `test_e2e.py`, antes del último:
      colores, radios y fuentes ya calculados por el navegador; Geist y Geist Mono cargadas desde este computador; un
      solo principal por zona con los resultados pintados; foco; los estados y los mensajes (vacío, error, aviso,
      listo, confirmación y tope); y 360 px sin desplazamiento horizontal.
- [x] **Paso 31 · Documentos y versión**: `README.md` (para Mac y Windows, sin «aún sin probar»; para qué productos
      sirve; Ajustes y escenas sin marca; la nota sin Google), `CAMBIOS.md` con la 1.1 (y los pendientes de la 1),
      `AGENTS.md` (la 1.1 y «Carpetas comunes» como el punto 3 de la ficha) e `inicio/index.html` con la 1.1, la
      versión en la herramienta, y ningún documento, prueba ni archivo de código con el negocio de ejemplo de la
      versión 1.
      Prueba: `test_estructura.py` (la 1.1 en `CAMBIOS.md`, `AGENTS.md`, la página de inicio y la herramienta; el
      README con «Para qué productos sirve» y sus dos avisos, sin «aún sin probar» y sin Google en la nota; el negocio
      de ejemplo y sus colores no aparecen en ningún archivo del proyecto).

## Pruebas, revisión y entrega

- [ ] **Paso 32 · Pruebas**: todas (rápidas, modelo real y punta a punta) → `PRUEBAS.md` actualizado: cuántas pasan,
      cuánto tardan, el tiempo por foto con las muestras de la guía 1.1 y la aceleración medida otra vez; se conservan
      los seis controles y lo que no se probó.
- [ ] **Paso 33 · Revisión corta**: el Revisor comprueba los puntos de seguridad que tocan estos cambios (el 9, la
      página no carga nada de internet, tampoco las fuentes; y el 8, el 5, el 3, el 2 y el 6) y que las pruebas pasan
      todas; escribe su parte en `REVISION.md`; se corrige lo que encuentre y lo vuelve a comprobar.
- [ ] **Paso 34 · Demo y entrega**: arrancar la herramienta, dar la dirección, el resumen final y la línea
      `TERMINADO: estudio-fotos 1.1`.
