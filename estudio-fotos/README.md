# Estudio de fotos de producto

Versión 1 · hecha con la ficha 1 de «Construyamos con IA» (guía de Ismagit).

Convierte las fotos de tus productos en fotos listas para vender: sin fondo, con fondo blanco puro, en las medidas de
cada tienda online y, si quieres, en escenas hechas con IA. Funciona solo en este computador.

## Cómo se abre

Lo más fácil: dile a tu agente de IA **«Abre el estudio de fotos»**.

A mano, desde la carpeta `herramientas-ia`, con el mismo comando en Mac, Linux y Windows:

```
uv run --directory estudio-fotos python -m estudio
```

- La primera vez tarda un poco más: prepara el entorno y descarga las librerías.
- Al arrancar escribe la dirección («Estudio de fotos abierto en http://127.0.0.1:8601») y abre el navegador.
- Si el puerto 8601 está ocupado, usa el siguiente libre y lo dice: «El puerto 8601 está ocupado: usamos el 8602.»
- Para cerrarla: `Ctrl` + `C` en esa ventana.
- La página solo se puede abrir desde este computador.

## Cómo se usa

La página tiene tres zonas: **Fotos**, **Resultados** y **Ajustes**.

### 1 · Sube tus fotos

Arrastra las fotos o haz clic para elegirlas: JPG, PNG o WEBP, hasta 20 a la vez y hasta 25 MB cada una.

- Si el lado corto mide menos de 500 px, la foto no se acepta. Si mide menos de 1.000 px, se acepta con un aviso.
- Las fotos HEIC del iPhone no se aceptan: expórtalas como JPG, o en el iPhone ve a Ajustes › Cámara › Formatos y elige
  «Más compatible».

### 2 · Recortes, antes y después

El fondo se quita en tu computador: es gratis y tus fotos no salen de él. La barra dice por dónde va
(«3 de 5 · foto_3.jpg · 4,2 s»). En cada foto, mueve la línea para comparar el antes y el después; el fondo de cuadros
es la parte transparente.

La primera vez se descarga el modelo de recorte (973 MB el completo, 224 MB el ligero). Solo pasa una vez, y mientras
tanto el resto de la página sigue funcionando.

### 3 · Fondo blanco y medidas

Marca las fotos y las plataformas, y pulsa **Generar medidas**. Cada foto sale sobre blanco puro (255, 255, 255), con
el producto centrado. A las fotos no se les añade nada: ni texto, ni logo, ni bordes.

| Plataforma | Medida | El producto ocupa | Peso máximo |
|---|---|---|---|
| Mercado Libre | 1200×1200 | 95 % | 10 MB |
| Amazon | de 1000×1000 a 2000×2000, sin ampliar | 85 % | no publica uno |
| Shopify | 2048×2048 | 85 % | 20 MB |
| Tiendanube | 1280×1280 | 85 % | 500 KB |
| Instagram (feed) | 1080×1350 | 80 % | no publica uno |
| Catálogo de Facebook e Instagram | 1024×1024 | 85 % | 8 MB |
| WhatsApp Business (catálogo) | 1024×1024 | 85 % | 8 MB |
| Google Merchant Center | 1500×1500 | 85 % | 16 MB |

Amazon pide no agrandar las fotos pequeñas: la medida baja hasta 1000×1000 y, si aun así hay que ampliar el producto,
el archivo lleva un aviso.

Las medidas están en `plataformas.json`, que puedes editar: cada plataforma tiene su medida, su porcentaje, su peso
máximo, lo que pide y de dónde se leyó (el 13 de noviembre de 2026). Si una plataforma cambia sus reglas, cámbialo ahí.

### 4 · Escenas con IA (opcional)

Coloca tu producto en una escena: sobre una mesa de madera, en una cocina, con los colores de tu marca, en exterior, en
un estudio, o en la que tú describas. Eliges las fotos, la escena y el formato (1:1, 4:5 o 16:9).

- Necesita una clave de OpenRouter (en Ajustes) y cuesta dinero: unos 4 centavos de dólar por imagen con el modelo
  recomendado.
- **Antes de gastar** pulsas «Ver el costo» y la página dice, por ejemplo,
  «5 escenas · costo estimado 0,20 $ · ¿Generar?». Solo se gasta si confirmas. Al terminar ves el costo real.
- Si el costo supera lo que queda del tope de la sesión, o lo que queda en tu clave, no se gasta y la página lo dice.
- Cada gasto queda anotado en `gastos.jsonl` (fecha, modelo, costo estimado y costo real; nunca la clave).
- Las escenas se marcan «Para redes y fotos secundarias»: Mercado Libre, Amazon y Google piden fondo blanco en la foto
  principal.
- Cada escena lleva en sus metadatos la marca de «imagen hecha con IA» (IPTC). Google Merchant Center la exige: no la
  quites.
- Para una escena, a OpenRouter se envía tu producto ya recortado sobre fondo blanco. Es lo único que sale de tu
  computador, y solo cuando confirmas.

### Resultados

Una cuadrícula por foto: el recorte (PNG con transparencia), las medidas y las escenas. Puedes descargar todo en un
ZIP, o una sola plataforma. Cada ZIP trae un `resumen.csv` con el archivo, la plataforma, la medida, el peso, el
porcentaje que ocupa el producto y los avisos.

Si tu Excel separa las columnas con punto y coma y ves todo en una sola columna, abre el archivo con
«Datos › Desde texto» y elige la coma.

## Ajustes

- **Clave de OpenRouter**: pégala y pulsa «Guardar clave». Después solo se ve «••••» y sus 4 últimos caracteres. El
  botón **Probar** comprueba la conexión sin gastar: «Conexión correcta · límite 2,00 $ · usado 0,12 $». La clave se
  guarda en el archivo `.env` de `herramientas-ia`, solo en este computador. Ponle un tope de gasto a la clave en
  openrouter.ai.
- **Marca del negocio**: nombre, color principal, color de acento y logo (opcional). La página usa esos colores; a las
  fotos nunca se les añade el logo.
- **Calidad del recorte**: Automática (recomendada), Máxima (el modelo completo) o Rápida (el modelo ligero). En un Mac
  con chip Apple o en un PC con tarjeta NVIDIA, Automática usa el modelo completo; en los demás, el ligero, y la página
  lo dice. Después del primer lote, la herramienta mide una sola vez si la aceleración de tu computador es más rápida
  que el procesador y se queda con lo más rápido; aquí mismo dice lo que salió.
- **Escenas con IA**: el modelo y el tope de gasto por sesión (1 $ si no lo cambias). La sesión dura desde que abres la
  herramienta hasta que la cierras.

## Dónde queda cada cosa

| Qué | Dónde |
|---|---|
| Tus resultados | `estudio-fotos/salidas/<fecha_hora>/`: `recortes/`, una carpeta por plataforma y `escenas/` |
| Los gastos en escenas | `estudio-fotos/gastos.jsonl` |
| Tus ajustes (sin la clave) | `estudio-fotos/ajustes.json` y `estudio-fotos/logo_negocio.png` |
| La clave | el archivo `.env` de `herramientas-ia` |
| Las medidas de cada plataforma | `estudio-fotos/plataformas.json` (lo puedes editar) |
| Lo medido de la aceleración | `estudio-fotos/medicion.json` (bórralo para volver a medir) |
| Los archivos temporales | `estudio-fotos/trabajo/` (se vacía al abrir y al cerrar la herramienta) |
| El modelo de recorte | `herramientas-ia/modelos/` (lo comparten todas las herramientas) |

La herramienta nunca borra tus resultados: «Quitar» y «Empezar de nuevo» vacían la lista de la página, y lo que ya
estaba en `salidas/` se queda. Cada vez que abres la herramienta (o pulsas «Empezar de nuevo»), los resultados van a
una carpeta nueva con su fecha y hora, y una escena nueva nunca pisa a una anterior.

Abre una sola copia a la vez. Una segunda copia arranca en el puerto siguiente, pero vacía los archivos temporales de
la primera (sus fotos dejarían de verse) y lleva su propia cuenta del tope de gasto.

## Cómo saber si funciona bien: seis controles

1. **Recorte limpio**: sin restos del fondo y sin bordes mordidos, también en pliegues, asas y zonas transparentes.
2. **Blanco puro**: todo el fondo es blanco 255, 255, 255, sin grises.
3. **Encuadre**: el producto está centrado y ocupa lo que pide la plataforma.
4. **Medidas y peso**: cada archivo tiene la medida, el formato y el peso de su plataforma.
5. **Escena fiel**: en las escenas con IA, la etiqueta, el texto, el logo y la forma del producto no cambian.
6. **Costo honesto**: el costo real coincide con el que la herramienta anunció antes de gastar.

## Cuánto cuesta

- Quitar el fondo, el fondo blanco y las medidas: nada.
- Las escenas con IA: lo que cobre OpenRouter por cada imagen (el costo de partida de cada modelo se ve en Ajustes, y
  se corrige con lo que cuestan de verdad tus escenas).

## Privacidad

- La herramienta solo escucha en este computador (`127.0.0.1`) y la página no carga nada de internet.
- Solo se conecta a internet para tres cosas: instalar las librerías, descargar el modelo de recorte y llamar a
  OpenRouter cuando confirmas unas escenas (o pulsas «Probar»).
- La clave no aparece en la página, en los registros ni en los mensajes de error.
- La ventana donde la abriste no muestra la clave ni la ruta de tu carpeta personal: tampoco durante la descarga del
  modelo ni cuando algo falla.
- Las fotos que subes se copian a `trabajo/` mientras la herramienta está abierta; al cerrarla se borran de ahí. Tus
  resultados se quedan en `salidas/`.
- La herramienta no pide contraseña. Mientras está abierta, otro usuario o programa de este mismo computador podría
  usarla y gastar con tu clave (verla, no). Si compartes el computador, ciérrala al terminar.

## Si algo falla

| Lo que ves | Qué hacer |
|---|---|
| «Este archivo no es una foto JPG, PNG o WEBP.» | Exporta la foto en uno de esos formatos. |
| «La foto mide N px de lado corto: se necesitan al menos 500.» | Usa una foto más grande. |
| «La foto pesa N MB: el máximo es 25.» | Expórtala con menos peso. |
| «No se puede abrir esta foto: puede estar dañada.» | Vuelve a exportarla o usa otra. |
| «No encontramos un producto claro en esta foto…» | Prueba con el producto más grande y un fondo más simple. |
| «No se pudo descargar el modelo de recorte…» | Revisa tu conexión y pulsa «Volver a intentarlo». |
| «Para las escenas con IA falta la clave de OpenRouter: ponla en Ajustes.» | Guarda tu clave en Ajustes. |
| «OpenRouter no acepta esta clave. Revísala en Ajustes.» | Copia la clave otra vez desde openrouter.ai. |
| «Se acabó el saldo o el límite de tu clave de OpenRouter.» | Recarga saldo o sube el límite de la clave en openrouter.ai. |
| «Esto costaría X $ y en esta sesión te quedan Y $…» | Sube el tope en Ajustes o genera menos escenas. |
| «OpenRouter pide esperar un momento. Lo intentamos de nuevo en N s.» | Nada: la herramienta lo reintenta sola. |
| «La escena no se pudo generar y no se cobró. Inténtalo otra vez.» | Vuelve a pedirla. |
| «El modelo no está disponible ahora…» | Prueba en unos minutos o elige otro modelo en Ajustes. |
| «El modelo no quiso generar esta escena…» | Prueba con otra descripción. |
| «Sin conexión a internet: el recorte sigue funcionando, las escenas con IA no.» | Revisa tu conexión. |
| «OpenRouter no respondió a tiempo…» | Antes de repetir, mira en openrouter.ai si se cobró. |
| La página dice que la herramienta no responde | Comprueba que la ventana donde la abriste sigue abierta y recarga. |

## Si usas Windows

- Pon `herramientas-ia` en tu carpeta de usuario, fuera de OneDrive: la sincronización bloquea archivos y subiría el
  modelo a la nube.
- El antivirus puede hacer lenta la primera carga del modelo.
- Con una tarjeta NVIDIA puedes abrir la versión acelerada con este otro comando:
  `uv run --directory estudio-fotos --no-default-groups --group gpu python -m estudio`.
  Puede necesitar CUDA y cuDNN instalados: si no están, la herramienta usa el procesador y lo dice.
- Esta versión se probó en Mac; en Windows, aún sin probar.

## Para quien la mantiene

Las pruebas usan simuladores y una carpeta temporal: nunca llaman a OpenRouter de verdad ni tocan tus archivos. Se
pasan desde `herramientas-ia`:

```
uv run --directory estudio-fotos --group pruebas pytest               # las rápidas
uv run --directory estudio-fotos --group pruebas pytest -m modelo     # con el modelo real de recorte
uv run --directory estudio-fotos --group pruebas pytest -m e2e        # de punta a punta, con el navegador
```

Las de punta a punta necesitan Chromium, que se instala una vez dentro de la carpeta (`estudio-fotos/.navegadores/`).
En Mac y Linux, desde la carpeta `estudio-fotos`:

```
PLAYWRIGHT_BROWSERS_PATH="$PWD/.navegadores" uv run --group pruebas playwright install chromium-headless-shell
```

Los demás documentos: `PLAN.md` (arquitectura y decisiones), `TAREAS.md` (los pasos), `PRUEBAS.md` (resultados y
tiempos), `REVISION.md` (la revisión de seguridad) y `CAMBIOS.md` (las versiones).
