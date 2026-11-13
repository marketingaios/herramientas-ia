# Estudio de fotos de producto

**Construyamos con IA · ficha 1 · versión 1 · noviembre de 2026 · guía de Ismagit**

Probado en Mac; en Windows, aún sin probar.

Esta ficha es todo lo que tu agente de IA (Claude Code, Codex u OpenCode) necesita para construir en tu computador una
herramienta que convierte las fotos de tus productos en fotos listas para vender: sin fondo, con fondo blanco, en las
medidas de cada tienda online y, si quieres, en escenas hechas con IA.

---

## Para ti

### Qué hace

1. Subes las fotos de tus productos, varias a la vez.
2. Quita el fondo en tu computador: gratis, y tus fotos no salen de tu computador.
3. Pone el producto sobre fondo blanco puro, centrado, en las medidas de Mercado Libre, Amazon, Shopify, Tiendanube,
   Instagram, el catálogo de Facebook e Instagram, WhatsApp Business y Google.
4. Si quieres, crea escenas con IA: tu producto sobre una mesa, en una cocina, con los colores de tu marca. Antes de
   gastar, te dice cuánto cuesta.
5. Descargas todo en un ZIP.

### Qué necesitas

- Un computador con Mac o Windows y unos 3 GB libres: el modelo de recorte, las librerías y tus fotos.
- Un agente de IA para programar (Claude Code, Codex u OpenCode), con el plan que ya tienes.
- Solo para las escenas con IA: una clave de OpenRouter, con un tope de gasto. El recorte y el fondo blanco no la
  necesitan.

### Cuánto cuesta

- Quitar el fondo, el fondo blanco y las medidas: nada, todo pasa en tu computador.
- Las escenas con IA: unos 4 centavos de dólar por imagen con el modelo recomendado, y la herramienta te dice el costo
  antes de gastar.
- Construirla: lo que use tu agente de tu plan.

### Cómo empezar

1. Crea una carpeta llamada `herramientas-ia` en tu carpeta personal. En Windows, fuera de OneDrive.
2. Pon dentro este archivo (`instrucciones.md`) y las carpetas `muestras` y `marca` de la guía.
3. Abre tu agente en esa carpeta y escribe: **Lee instrucciones.md y construye la herramienta**.
4. Cuando termine, escribe: **Abre el estudio de fotos**.
5. En la página, entra en **Ajustes**: pon el nombre y los colores de tu negocio y, si quieres escenas con IA, tu clave
   de OpenRouter.

Las fotos de `muestras` son de un negocio de ejemplo, Café 2600, y están hechas con IA.

### Cómo saber si funciona bien: seis controles

1. **Recorte limpio**: sin restos del fondo y sin bordes mordidos, también en las partes difíciles (pliegues, asas,
   zonas transparentes).
2. **Blanco puro**: todo el fondo es blanco 255, 255, 255, sin grises.
3. **Encuadre**: el producto está centrado y ocupa lo que pide la plataforma.
4. **Medidas y peso**: cada archivo tiene la medida, el formato y el peso de su plataforma.
5. **Escena fiel**: en las escenas con IA, la etiqueta, el texto, el logo y la forma del producto no cambian.
6. **Costo honesto**: el costo real coincide con el que la herramienta anunció antes de gastar.

---

## Para el agente

Lee toda la ficha antes de empezar. Trabaja solo dentro de la carpeta `herramientas-ia`.

### 1. Reglas fijas

**Datos sensibles**

- Nunca leas, muestres, copies ni busques el contenido de `.env`, y no crees ningún archivo `.env` (ni de ejemplo): la
  clave la escribe solo la página de Ajustes.
- La clave nunca va en el código, en los registros, en los mensajes de error, en las respuestas del servidor ni en las
  pruebas. En la página se ve solo como `••••` seguido de sus 4 últimos caracteres.
- Las pruebas nunca llaman a OpenRouter de verdad: usan un simulador.
- Las pruebas trabajan en una carpeta temporal: nunca leen ni escriben el `.env` real, `ajustes.json`, `salidas/` ni
  `gastos.jsonl`.
- Nada de datos personales en la página ni en los registros: ni nombres, ni correos, ni rutas de la carpeta personal.

**Solo en tu computador**

- El servidor escucha solo en `127.0.0.1`: nada de `0.0.0.0`, túneles ni publicación.
- La página no carga nada de internet (ni fuentes, ni librerías, ni iconos): todo está en la carpeta.
- Las únicas conexiones a internet son tres: instalar las dependencias, descargar el modelo de recorte y llamar a
  OpenRouter cuando el usuario lo confirma.

**Gasto**

- Una sola clave, la de OpenRouter, para toda la IA.
- Antes de cada gasto, la página muestra el costo estimado y pide confirmar. Después, muestra el costo real.
- Hay un tope de gasto por sesión en Ajustes (1 $ por defecto): si la estimación lo supera, no se gasta.

**Para quien la usa**

- Todo en español: la página, los mensajes, los errores y el README.
- Los trabajos van en lote, con barra de avance.
- Los errores dicen qué pasó y qué hacer (punto 5).
- La firma de Ismagit va en el pie de cada página (punto 4.7), nunca dentro de las fotos.
- Si existe la variable de entorno `NO_ABRIR_NAVEGADOR=1`, la herramienta no abre el navegador (sirve para las pruebas
  automáticas y para trabajar en un servidor).

### 2. Método: ingeniería con agentes, no improvisación

Trabaja por fases. Al empezar cada una, escribe una línea sola con su nombre:

`Fase · Ficha` → `Fase · Plan` → `Fase · Construcción` → `Fase · Pruebas` → `Fase · Revisión` → `Fase · Demo`

1. **Ficha**: lee esta ficha y guarda una copia en `estudio-fotos/FICHA.md`.
2. **Plan**: escribe `estudio-fotos/PLAN.md` (arquitectura, archivos, dependencias con su versión, riesgos y
   decisiones) y `estudio-fotos/TAREAS.md` (pasos pequeños, cada uno con su prueba, con casillas `- [ ]`). El
   **Revisor** compara el plan con la ficha y anota lo que falta o sobra. Corrige antes de seguir.
3. **Construcción**: un paso de `TAREAS.md` a la vez. Cada paso tiene su prueba, y las pruebas anteriores deben seguir
   pasando. Al terminar un paso, marca su casilla y haz **un commit** con un mensaje claro en español («Paso 4: fondo
   blanco y encuadre»).
4. **Pruebas**: todas las pruebas, también las de punta a punta con el navegador (punto 6). Anota los resultados y los
   tiempos en `estudio-fotos/PRUEBAS.md`.
5. **Revisión**: el Revisor hace la revisión de seguridad (punto 7) y escribe `estudio-fotos/REVISION.md`. Corrige lo
   que encuentre, vuelve a pasar las pruebas y haz el commit. Si hubo correcciones, el Revisor hace una segunda vuelta
   corta: comprueba solo lo corregido y sus pruebas, no los 10 puntos desde cero.
6. **Demo**: arranca la herramienta (punto 8) y da la dirección.

**Roles**

- **Constructor** (tú): planifica, programa y prueba.
- **Revisor**: un subagente con el contexto limpio, o un segundo modelo, que lee la ficha, el plan y el código y no
  escribe código. Si tu agente no puede crear subagentes, haz la revisión en un paso aparte, releyendo la ficha desde
  cero.

**Decisiones y preguntas**

- No hagas preguntas: si algo no está claro, elige la opción más simple y anótala en `PLAN.md`, en «Decisiones».
- Pide permiso solo para instalar algo fuera de la carpeta (por ejemplo uv o git) o para gastar dinero.
- Usa git en `herramientas-ia`; si no hay repositorio, créalo. Si git no está instalado y no lo puedes instalar, sigue
  y anota los pasos en `CAMBIOS.md`.

### 3. La carpeta `herramientas-ia`

Puede que sea la primera herramienta o que ya haya otras: **no borres ni cambies lo que ya existe**, solo añade.

```
herramientas-ia/
├── AGENTS.md          cómo se trabaja aquí y cómo se abre cada herramienta
├── CLAUDE.md          una sola línea: @AGENTS.md
├── .env               las claves: lo escribe Ajustes, nunca se lee ni va a git
├── .gitignore         .env, modelos/, */trabajo/, */salidas/, gastos, entornos virtuales y cachés
├── instrucciones.md   esta ficha
├── muestras/          fotos de ejemplo (Café 2600)
├── marca/             los logos de Ismagit para la firma y el de Café 2600, para probar Ajustes
├── estilo/            estilo.css común (los colores de la marca como variables) y la firma
├── modelos/           los modelos descargados, compartidos por todas las herramientas
├── inicio/index.html  la página de inicio: la lista de herramientas, con su dirección
└── estudio-fotos/     esta herramienta
```

**`AGENTS.md`** dice, en español y en pocas líneas:

- qué es esta carpeta, las reglas fijas (punto 1, resumidas) y el método (punto 2);
- una tabla de herramientas con el nombre, la carpeta, la versión, la dirección y cómo abrirla en Mac o Linux y en
  Windows;
- que cuando el usuario pide «Abre …», el agente arranca esa herramienta en segundo plano con su comando, espera a que
  responda y da la dirección.

**`estudio-fotos/`** tiene además:

- `README.md`: cómo se abre y cómo se usa, para el dueño del negocio;
- `CAMBIOS.md`: la versión 1;
- `PLAN.md`, `TAREAS.md`, `PRUEBAS.md` y `REVISION.md`;
- `plataformas.json`;
- las pruebas;
- `trabajo/` (archivos temporales) y `salidas/` (los resultados).

### 4. Qué construyes

Una página web en `http://127.0.0.1:8601` con tres zonas: **Fotos**, **Resultados** y **Ajustes**. Si el puerto 8601
está ocupado, usa el siguiente libre y dilo.

**Tecnología recomendada** (si cambias algo, explica por qué en `PLAN.md`):

- Python 3.11, 3.12 o 3.13 (el README de rembg pide una versión anterior a la 3.14) con uv: proyecto con `pyproject.toml` y `uv.lock`, todas
  las versiones fijadas;
- FastAPI y uvicorn para el servidor;
- Pillow para las imágenes;
- rembg (licencia MIT) con onnxruntime para el recorte: `rembg[cpu]` por defecto, y `rembg[gpu]` solo en un PC con
  tarjeta NVIDIA, como opción aparte;
- httpx para OpenRouter;
- la página en HTML, CSS y JavaScript, sin compilación y sin librerías de internet;
- las pruebas con pytest, un servidor falso para OpenRouter y Playwright para Python con Chromium.

#### 4.1 Subir

- Se arrastran o se eligen las fotos: JPG, PNG o WEBP, hasta 20 a la vez y hasta 25 MB cada una.
- El tipo se comprueba por el contenido del archivo, no por el nombre.
- Si el lado corto mide menos de 500 px, la foto no se acepta. Si mide menos de 1.000 px, se acepta con un aviso.
- Una foto HEIC (iPhone) tiene su mensaje con la solución (punto 5).

#### 4.2 Quitar el fondo, en el computador

- El modelo es BiRefNet (licencia MIT), con rembg. Pídelo siempre por su nombre: `birefnet-general` (el completo, unos
  973 MB) o `birefnet-general-lite` (el ligero, unos 224 MB). **Nunca** llames a `new_session()` sin nombre: rembg usaría
  `bria-rmbg`, cuya licencia no permite el uso comercial.
- Crea la sesión una sola vez y úsala para todo el lote.
- Los modelos se descargan en `herramientas-ia/modelos/` con la variable `REMBG_HOME` (comprueba en el código de rembg
  qué carpeta usa esa variable), y la página lo muestra:
  «Descargando el modelo de recorte (973 MB), solo la primera vez». Mientras, el resto de la página sigue funcionando.
- El modelo se adapta al computador:
  - Mac con chip Apple, o PC con tarjeta NVIDIA: el modelo completo («Calidad máxima»);
  - los demás: el modelo ligero, y la página lo dice: «Modo rápido: tu computador no tiene aceleración y usamos un
    modelo más ligero. Puedes cambiarlo en Ajustes.»
- La aceleración se mide, no se supone:
  - en un Mac con chip Apple, rembg no usa CoreML por sí solo: prueba a pasarle
    `providers=[("CoreMLExecutionProvider", {"ModelFormat": "MLProgram"}), "CPUExecutionProvider"]`, **una sola vez y
    con un tiempo máximo de 2 minutos** para preparar el modelo. En las pruebas de esta guía (Mac con chip Apple,
    noviembre de 2026) CoreML no sirvió con BiRefNet: el modo MLProgram falló al preparar el modelo y el modo clásico
    pasó de 7 minutos. El procesador hizo unos 8 s por foto con el modelo completo y unos 6 s con el ligero;
  - mide el tiempo de una foto con lo que funcione, quédate con lo más rápido y anótalo en `PRUEBAS.md`;
  - si la aceleración falla o tarda más que el tiempo máximo, sigue con el procesador, sin romper el lote.
- Las fotos se procesan en cola, una tras otra, con la barra: «3 de 5 · foto_3.jpg · 4,2 s».
- Cada resultado se ve antes y después, con un deslizador, y el recorte sobre un fondo de cuadros.

#### 4.3 Fondo blanco y medidas

Para cada foto y cada plataforma elegida:

- fondo blanco puro, `#FFFFFF` (255, 255, 255), sin sombras;
- el producto entero, centrado, ocupando el porcentaje de la plataforma (en el lado más largo del producto);
- la medida, el formato y el peso máximo de la plataforma: JPEG en sRGB con calidad 90, que baja si el archivo supera
  el peso;
- nunca se añade texto, logo, borde ni marca de agua a las fotos (Mercado Libre, Amazon, Google y Meta lo prohíben);
- **Amazon pide no agrandar artificialmente las fotos pequeñas**: para Amazon, la medida baja hasta la que no amplía el
  producto, con un mínimo de 1000×1000; si aun así hay que ampliarlo, el archivo lleva un aviso;
- en las demás, si el producto se tuvo que ampliar más del doble, el archivo lleva un aviso: «ampliada ×2,4, puede
  verse borrosa»;
- el nombre `<foto>_<plataforma>_<ancho>x<alto>.jpg`.

Donde la plataforma no publica un peso máximo, la herramienta no pone uno.

Las plataformas van en `plataformas.json`, que el usuario puede editar, con estos valores (fuentes oficiales leídas el
13/11/2026):

| Plataforma | Exporta | Producto | Peso máximo | Lo que dice la plataforma | Fuente |
|---|---|---|---|---|---|
| Mercado Libre | 1200×1200 | 95 %, sin márgenes | 10 MB | fondo blanco puro hecho en digital; la primera foto sin contexto ni empaque; sin logos, textos, marcas de agua ni bordes | mercadolibre.com.mx/ayuda/805 y developers.mercadolibre.com.ar/trabajar-con-imagenes |
| Amazon | de 1000×1000 a 2000×2000, sin ampliar | 85 %, entero | no lo publica | fondo 255, 255, 255; de 500 a 10.000 px en el lado más largo; desde 1000 hay zoom; sin texto ni precios | sellercentral.amazon.com.mx, guía G1881 |
| Shopify | 2048×2048 | 85 % (no lo dice) | 20 MB | hasta 5000×5000; la misma proporción en todas las fotos principales | help.shopify.com, «product media types» |
| Tiendanube | 1280×1280 | 85 % (no lo dice) | 500 KB | recomienda 100-500 KB por foto; la plataforma no adapta las fotos | ayuda.tiendanube.com, «cómo adaptar el tamaño» |
| Instagram (feed) | 1080×1350 (4:5) | 80 % (no lo dice) | no lo publica | 1080 de ancho, de 1,91:1 a 3:4 | help.instagram.com/1631821640426723 |
| Catálogo de Facebook e Instagram | 1024×1024 | 85 %, entero | 8 MB | fondo blanco recomendado; sin textos sobre el producto, llamadas a la acción, códigos ni marcas de agua | facebook.com/business/help/686259348512056 |
| WhatsApp Business (catálogo) | 1024×1024 | 85 % | 8 MB | WhatsApp no publica medidas: usamos las del catálogo de Meta, que se puede conectar a WhatsApp | faq.whatsapp.com/405903568419894 |
| Google Merchant Center | 1500×1500 | 85 % (pide entre 75 % y 90 %) | 16 MB | mínimo 500×500, obligatorio desde el 31/01/2027; sin llamadas a la acción, precios, marcas de agua, logos añadidos ni bordes | support.google.com/merchants/answer/6324350 |

#### 4.4 Escenas con IA (opcional)

- Funcionan con la clave de OpenRouter.
- Se eligen fotos ya recortadas, una escena y el formato (1:1, 4:5 o 16:9). Hay 5 escenas preparadas, que sirven a
  cualquier negocio, y el campo para escribir la tuya:
  - «Mesa de madera clara con luz de mañana»;
  - «Cocina moderna, encimera de piedra»;
  - «Fondo liso con los colores de tu marca»;
  - «Exterior con luz natural suave»;
  - «Estudio con sombra suave».
- Los modelos, en Ajustes (los ids de OpenRouter; el costo de partida por imagen de 1K, que se corrige con los costos
  reales):

  | Modelo | id en OpenRouter | Costo de partida |
  |---|---|---|
  | Nano Banana 2.1 (recomendado) | `google/gemini-nano-banana-2.1` | 0,04 $ (medido el 13/11/2026: 0,038 $ con una foto de entrada) |
  | Nano Banana 2 Lite | `google/gemini-3.1-flash-lite-image` | 0,04 $ |
  | Nano Banana 2 | `google/gemini-3.1-flash-image` | 0,07 $ |
  | Nano Banana Pro | `google/gemini-3-pro-image` | 0,14 $ |

- La petición: `POST https://openrouter.ai/api/v1/images` con `model`, `prompt`, `aspect_ratio`, `resolution: "1K"` y el
  producto sobre fondo blanco en `input_references`, como data URL en base64:
  `[{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,…"}}]`. La imagen vuelve en `data[0].b64_json` y
  el costo real en `usage.cost`. Una generación que falla devuelve 502 y no se cobra.
- El texto fijo de la petición pide usar exactamente el producto de la imagen, sin cambiar la etiqueta, el texto, el
  logo, la forma ni los colores, y sin añadir textos ni marcas de agua.
- Antes de gastar: «5 escenas · costo estimado 0,20 $ · ¿Generar?». El costo estimado es el de partida del modelo; en
  cuanto hay escenas hechas, la media de sus costos reales en `gastos.jsonl`. Después: el costo real.
- Cada gasto se anota en `estudio-fotos/gastos.jsonl`, una línea JSON por gasto: `ts` (fecha y hora ISO 8601 en UTC),
  `modelo`, `imagenes`, `costo_estimado_usd` y `costo_usd` (el real). Nunca la clave.
- Si la estimación supera lo que queda del tope de la sesión, o lo que queda en la clave, no se gasta, y la página lo
  dice.
- Las escenas llevan en sus metadatos la marca IPTC de imagen hecha con IA, en XMP: `Iptc4xmpExt:DigitalSourceType` con
  el valor `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`. Google Merchant Center la exige y
  prohíbe quitarla: se conserva también cuando la escena cambia de medida.
- En la página, las escenas se marcan «Para redes y fotos secundarias»: Mercado Libre, Amazon y Google piden fondo
  blanco en la foto principal.

#### 4.5 Resultados y descarga

- Una cuadrícula por foto: el recorte (PNG con transparencia), las medidas y las escenas.
- Se descarga todo en un ZIP, o una plataforma a la vez, con `resumen.csv`: archivo, plataforma, medida, peso, porcentaje
  ocupado por el producto y avisos.

#### 4.6 Ajustes

- **Clave de OpenRouter**: un campo de tipo contraseña. Al guardar, se escribe en `herramientas-ia/.env` (cambia solo esa
  línea y deja las demás). Después se ve «••••» y los 4 últimos caracteres, y el botón **Probar**, que consulta
  `GET https://openrouter.ai/api/v1/key` (`limit`, `limit_remaining` y `usage`) y responde, por ejemplo, «Conexión
  correcta · límite 2,00 $ · usado 0,12 $». La herramienta lee la clave del `.env` cada vez que la necesita: si cambia,
  no hace falta reiniciarla.
- **Marca del negocio**: nombre, color principal, color de acento y logo (opcional). La página usa esos colores.
- **Calidad del recorte**: Automática (recomendada), Máxima o Rápida.
- **Escenas**: el modelo y el tope de gasto por sesión.
- Los ajustes, sin la clave, se guardan en `estudio-fotos/ajustes.json`.

#### 4.7 Diseño

- Limpio, con la marca del negocio, y se lee bien en un portátil.
- Estados claros: vacío («Arrastra aquí tus fotos»), trabajando (la barra), terminado y error.
- En el pie de cada página, la firma de Ismagit: el logo pequeño de `marca/` y el texto «Hecho con la guía de Ismagit»,
  con enlace a `https://marketingaios.com/?origen=herramienta-estudio-fotos`.

### 5. Mensajes de error

| Situación | Mensaje |
|---|---|
| Formato no admitido | «Este archivo no es una foto JPG, PNG o WEBP.» |
| Foto HEIC | «Es una foto HEIC (iPhone). Expórtala como JPG, o en el iPhone ve a Ajustes › Cámara › Formatos y elige «Más compatible».» |
| Foto pequeña | «La foto mide N px de lado corto: se necesitan al menos 500.» |
| Foto demasiado grande | «La foto pesa N MB: el máximo es 25.» |
| Foto dañada | «No se puede abrir esta foto: puede estar dañada.» |
| Sin producto | «No encontramos un producto claro en esta foto. Prueba con el producto más grande y un fondo más simple.» |
| Modelo descargándose | «Descargando el modelo de recorte, solo la primera vez…» |
| Descarga del modelo fallida | «No se pudo descargar el modelo de recorte. Revisa tu conexión y vuelve a intentarlo.» |
| Sin clave | «Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes.» |
| Clave no válida (401) | «OpenRouter no acepta esta clave. Revísala en Ajustes.» |
| Sin saldo o límite de la clave agotado | «Se acabó el saldo o el límite de tu clave de OpenRouter.» |
| Tope de la sesión | «Esto costaría X $ y en esta sesión te quedan Y $. Sube el tope en Ajustes o genera menos escenas.» |
| Demasiadas peticiones (429) | «OpenRouter pide esperar un momento. Lo intentamos de nuevo en N s.» |
| Generación fallida (502) | «La escena no se pudo generar y no se cobró. Inténtalo otra vez.» |
| Sin proveedor (503) | «El modelo no está disponible ahora. Prueba en unos minutos o elige otro en Ajustes.» |
| Foto rechazada por el modelo (400) | «El modelo no aceptó esta foto. Prueba con otra o con una más pequeña.» |
| Filtro de contenido | «El modelo no quiso generar esta escena. Prueba con otra descripción.» |
| Sin conexión | «Sin conexión a internet: el recorte sigue funcionando, las escenas con IA no.» |
| Puerto ocupado | «El puerto 8601 está ocupado: usamos el N.» |

Con OpenRouter, decide por el código HTTP y por `error.metadata.limit_source`, nunca por el texto del mensaje:

- 402, o 403 con `limit_source` igual a `openrouter_key_limit` u `openrouter_credits`: saldo o límite agotado (la
  documentación de OpenRouter da los dos códigos para el límite de la clave);
- 402 con `openrouter_in_flight_budget`: espera lo que diga `Retry-After` y reintenta, salvo si `reason` es
  `weight_exceeds_budget` (reintentar no sirve);
- 403 con `content_policy_violation`: el filtro de contenido.

### 6. Pruebas

**Rápidas**, sin internet y con un recortador simulado (pytest):

- fondo blanco, encuadre (el porcentaje con ±1 % y el centro con ±1 %), medida y peso de cada plataforma, la regla de
  Amazon (sin ampliar), nombres de archivo, ZIP y `resumen.csv`;
- la clave: se guarda en `.env`, se ve enmascarada y ninguna respuesta del servidor la contiene; después de una prueba
  con una clave falsa, ningún registro, resultado ni página la contiene;
- el costo: la estimación es correcta, y con el tope superado no se llama a OpenRouter;
- OpenRouter simulado: éxito, clave no válida, sin saldo (402 y 403), demasiadas peticiones, generación fallida y sin
  conexión, cada uno con su mensaje;
- las escenas guardadas llevan la marca IPTC de imagen hecha con IA;
- las subidas: formato, tamaño y foto dañada.

**Con el modelo real**, aparte (la primera vez descarga el modelo): recorta las 5 fotos de `muestras/`, comprueba que
cada recorte tiene un producto (la máscara ocupa entre el 5 % y el 95 % de la foto) y anota el tiempo por foto.

**De punta a punta**, con Playwright y Chromium sin ventana, y el servidor arrancado en otro puerto con
`NO_ABRIR_NAVEGADOR=1`:

1. abre la página, sube las 5 fotos de `muestras/`, espera la barra hasta «5 de 5» y ve los 5 recortes;
2. elige Mercado Libre, Amazon e Instagram, genera, descarga el ZIP y comprueba los archivos;
3. en Ajustes guarda una clave falsa, ve «••••» con los 4 últimos caracteres, pulsa Probar (simulado) y ve «Conexión
   correcta»;
4. pide 2 escenas con OpenRouter simulado: ve el costo estimado antes, confirma, ve las 2 escenas y el costo real.

Para que las pruebas usen el simulador, la dirección de OpenRouter se puede cambiar con una variable de entorno, solo
para las pruebas. Todo debe pasar antes de la Revisión. En `PRUEBAS.md`: cuántas pruebas pasan, cuánto tardan y el
tiempo por foto en este computador.

### 7. Revisión de seguridad

El Revisor comprueba cada punto y escribe en `REVISION.md` «Bien» o «Corregido», con el detalle:

1. el servidor escucha solo en `127.0.0.1`, y una prueba lo comprueba;
2. no hay ninguna clave en el código, en el historial de git, en los registros, en las salidas, en las respuestas ni en
   los errores (busca también los patrones de las claves de OpenRouter);
3. `.env`, `modelos/`, `trabajo/`, `salidas/` y `gastos.jsonl` están fuera de git;
4. las dependencias tienen la versión fijada (`uv.lock`);
5. las subidas comprueban el tipo por el contenido, el tamaño y los píxeles (las «bombas de descompresión»), y los nombres
   se limpian (sin rutas);
6. las únicas conexiones son la descarga del modelo y openrouter.ai;
7. no hay `shell=True`, `eval` ni `exec` con datos del usuario;
8. la herramienta escribe solo dentro de `herramientas-ia`, y `.env` queda legible solo por el usuario (en Mac y Linux,
   permisos 600);
9. la página no carga nada de internet;
10. el recorte nunca usa `bria-rmbg` (el nombre del modelo va siempre explícito).

Al final, el veredicto: «Aprobada», o la lista de lo corregido y las pruebas pasadas de nuevo.

### 8. Abrir la herramienta

- Un solo comando de arranque, que funciona igual en Mac, Linux y Windows (por ejemplo, con `uv run`). Escríbelo en
  `AGENTS.md` y en el `README.md`.
- El arranque prepara el entorno si falta, elige el puerto, arranca el servidor, espera a que responda, escribe la
  dirección y abre el navegador (salvo con `NO_ABRIR_NAVEGADOR=1`).
- Añade la herramienta a `inicio/index.html`: el nombre, para qué sirve y la dirección.

### 9. Entrega

Al terminar, escribe en el chat, en pocas líneas: qué construiste, cómo se abre, cuántas pruebas pasan, cuántos commits
hiciste, el veredicto del Revisor y el tiempo por foto en este computador. Después, una línea sola:

`TERMINADO: estudio-fotos`

### 10. Si usas Windows

- Pon `herramientas-ia` en tu carpeta de usuario (`C:\Users\<tu usuario>\herramientas-ia`), fuera de OneDrive: la
  sincronización bloquea archivos y subiría el modelo a la nube.
- Si faltan uv o Python, el agente usa el instalador oficial de uv para Windows, con tu permiso.
- Rutas con `pathlib` y archivos siempre en UTF-8.
- Con una tarjeta NVIDIA, la versión acelerada (`rembg[gpu]`) puede necesitar CUDA y cuDNN instalados: si no están, la
  herramienta usa el procesador y lo dice. No se instalan sin tu permiso.
- El antivirus puede hacer lenta la primera carga del modelo.

### 11. ¿Y si la quiero en internet?

Esta herramienta es para tu computador. Para ponerla en internet harían falta: entrar con usuario y contraseña, HTTPS,
un tope de gasto por persona, un servidor con potencia para el recorte y una política de privacidad para las fotos. Lo
veremos en otro episodio.

### 12. Ideas para la versión 2

- **Modo fiel**: la IA hace solo el fondo, y la herramienta pone encima tu producto original, así la etiqueta no puede
  cambiar.
- Una sombra natural bajo el producto.
- Textos alternativos y nombres de archivo pensados para el SEO.
- Procesar una carpeta entera.
- Exportar para el catálogo de Shopify o de Meta.
