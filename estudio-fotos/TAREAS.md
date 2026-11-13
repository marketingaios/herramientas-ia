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
- [ ] **Paso 3 · Subidas**: tipo por contenido, HEIC, peso, lado corto, megapíxeles, foto dañada, nombre limpio.
      Prueba: `test_subidas.py` (cada mensaje del punto 5; el aviso por debajo de 1.000 px; nombres con rutas).
- [ ] **Paso 4 · Fondo blanco y encuadre**: blanco 255, centrado, porcentaje, medida, JPEG sRGB, peso, regla de Amazon,
      aviso de ampliación, nombres de archivo.
      Prueba: `test_encuadre.py` (porcentaje ±1 %, centro ±1 %, medida y peso de cada plataforma, todo el fondo en 255).
- [ ] **Paso 5 · Recorte**: recortador con rembg y BiRefNet (nombre siempre explícito), recortador simulado, limpieza
      mínima de máscara, «sin producto», modelo según el computador.
      Prueba: `test_recorte.py` (simulado; elección del modelo; la limpieza no muerde; nunca `bria-rmbg`) y, con el
      modelo real, `test_modelo_real.py` (`-m modelo`: las 5 muestras, máscara entre el 5 % y el 95 %, el modelo queda
      en `modelos/`, tiempo por foto).
- [ ] **Paso 6 · El estudio y la cola de recorte**: fotos, nombres repetidos, avance «3 de 5 · foto_3.jpg · 4,2 s», una
      sola sesión por lote, un error no rompe el lote, estados de la descarga del modelo (descargando con su tamaño,
      fallida, reintento).
      Prueba: `test_cola.py`.
- [ ] **Paso 7 · Medidas en lote, resultados y descarga**: medidas por foto y plataforma, ZIP de todo o de una
      plataforma, `resumen.csv`.
      Prueba: `test_medidas.py`, `test_descargas.py`.
- [ ] **Paso 8 · Clave y ajustes**: `.env` (solo su línea, permisos 600, se lee cada vez), máscara, `ajustes.json`,
      colores `#RRGGBB`, logo validado, calidad del recorte, modelos de escenas y tope de 1 $.
      Prueba: `test_clave.py`, `test_ajustes.py` (con `marca/cafe2600_logo.png` como logo).
- [ ] **Paso 9 · OpenRouter**: cliente, simulador con el contrato exacto de la ficha, `/key`, errores por código y
      campos estructurados, reintentos.
      Prueba: `test_openrouter.py` (éxito; forma exacta de la petición; sin clave; 401; 402; 403 con
      `openrouter_key_limit` y con `openrouter_credits`; 402 en vuelo, con y sin `weight_exceeds_budget`; 403 con
      `content_policy_violation`; otro 403; 429 y reintentos agotados; 502; 503; 400; sin conexión; un texto de error
      engañoso no cambia el mensaje).
- [ ] **Paso 10 · Costos**: modelos y costo de partida, estimación con la media real, tope de la sesión,
      `gastos.jsonl`.
      Prueba: `test_costos.py` (estimación correcta; con el tope superado no se llama a OpenRouter; lo que queda en la
      clave; formato de los importes).
- [ ] **Paso 11 · Escenas**: texto fijo, las 5 escenas y la propia, colores de la marca, imagen de referencia, formato
      exacto sin ampliar ni deformar, marca IPTC, lote con costo real.
      Prueba: `test_escenas.py` (la marca IPTC está y se conserva al cambiar de medida).
- [ ] **Paso 12 · Servidor**: rutas de la API, estáticos, `Host`/`Origin`, CSP, errores en español, sin `/docs`.
      Prueba: `test_servidor.py` (incluye más de 20 fotos y cada ruta de más), `test_privacidad.py` (ninguna respuesta,
      registro, salida ni página contiene la clave falsa; el 422 no repite la entrada; sin rutas personales),
      `test_codigo.py` (sin `shell=True`, `eval` ni `exec`; las únicas direcciones de internet del código son
      openrouter.ai; el vigilante de los archivos reales).
- [ ] **Paso 13 · Arranque**: `python -m estudio`: puerto libre, solo `127.0.0.1`, espera, dirección,
      `NO_ABRIR_NAVEGADOR=1`.
      Prueba: `test_arranque.py` (elige el siguiente puerto libre y lo dice; el proceso responde y escribe la
      dirección; no escucha en otras interfaces; con `NO_ABRIR_NAVEGADOR=1` no abre el navegador).
- [ ] **Paso 14 · Página · Fotos**: subir y arrastrar, errores por archivo, avisos «Calidad máxima» y «Modo rápido…»,
      descarga del modelo, barra de avance, deslizador antes/después sobre fondo de cuadros, firma en el pie.
      Prueba: `test_pagina.py` (nada de internet salvo el enlace de la firma) y recorrido 1 de `test_e2e.py`.
- [ ] **Paso 15 · Página · Medidas y Resultados**: selector de plataformas, generar, cuadrícula por foto, avisos por
      archivo, descarga de todo o por plataforma.
      Prueba: recorrido 2 de `test_e2e.py` (Mercado Libre, Amazon e Instagram; ZIP comprobado).
- [ ] **Paso 16 · Página · Ajustes**: clave (••••, Probar, borrar), marca del negocio, calidad del recorte, modelo de
      escenas y tope.
      Prueba: recorrido 3 de `test_e2e.py`.
- [ ] **Paso 17 · Página · Escenas**: elegir fotos, escena y formato; costo estimado; confirmar; avance; costo real;
      «Para redes y fotos secundarias».
      Prueba: recorrido 4 de `test_e2e.py` (2 escenas con OpenRouter simulado).
- [ ] **Paso 18 · Aceleración medida**: prueba de CoreML en un subproceso con 2 minutos como máximo, `medicion.json`,
      se queda con lo más rápido.
      Prueba: `test_aceleracion.py` (falla → procesador; tarda demasiado → procesador; más rápida → se elige) y la
      medición real en este computador.
- [ ] **Paso 19 · Documentos**: `README.md`, `CAMBIOS.md`, tabla de `AGENTS.md`, `inicio/index.html`.
      Prueba: `test_estructura.py` ampliada (el comando de arranque aparece en `AGENTS.md` y en el `README.md`).

## Pruebas, revisión y entrega

- [ ] **Paso 20 · Pruebas**: todas (rápidas, modelo real y punta a punta) → `PRUEBAS.md` con cuántas pasan, cuánto
      tardan, el tiempo por foto y la medición de la aceleración.
- [ ] **Paso 21 · Revisión**: el Revisor comprueba los 10 puntos de seguridad y escribe `REVISION.md`; se corrige, se
      vuelven a pasar las pruebas y el Revisor comprueba lo corregido.
- [ ] **Paso 22 · Demo y entrega**: arrancar la herramienta, dar la dirección y el resumen final.
