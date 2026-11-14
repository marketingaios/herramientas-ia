# Cambios

## Versión 1.1 · 14 de noviembre de 2026

Hecha con la versión 1.1 de la ficha 1 de «Construyamos con IA» (guía de Ismagit), sobre la versión 1. Para Mac y
Windows.

**Qué cambia**

- **Diseño de Ismagit**: la página es oscura, con los colores de la ficha en `estilo/estilo.css`, el logo de Ismagit
  arriba a la izquierda junto a «Estudio de fotos», los botones principales en el acento (uno solo por zona) y las
  fuentes Geist y Geist Mono, que están en `estilo/fuentes/` con su licencia: la página sigue sin cargar nada de
  internet. Cada foto se ve sobre su fondo real: los recortes sobre cuadros claros y las fotos con fondo blanco sobre
  blanco. El foco del teclado se ve, el texto cumple el contraste AA y la página no se rompe en una pantalla estrecha.
- **Sin marca del negocio**: en Ajustes quedan solo la clave de OpenRouter, la calidad del recorte y las escenas. Se
  quitaron el nombre, los colores y el logo de la página, del servidor y de `ajustes.json`. La página ya no cambia de
  colores.
- **Escenas**: «Fondo liso con los colores de tu marca» pasa a ser «Fondo liso de un color», con un selector de color
  (gris claro si no se cambia). El color solo viaja en el texto de la petición de esa escena.
- **Muestras**: las pruebas usan todas las fotos de `muestras/`, sin contar con un número fijo. Con la guía 1.1 son
  seis: café (una bolsa y una taza), una zapatilla, un bolso, una camiseta y un frasco de vidrio.
- **Para Mac y Windows**: el README lo dice así, y cuenta para qué productos sirve la herramienta.
- **Versión**: la 1.1 en `AGENTS.md`, en la página de inicio y en la herramienta.

**Si vienes de la versión 1**

- La primera vez que se abre, la herramienta quita la marca del negocio de `ajustes.json` (la calidad del recorte, el
  modelo de escenas y el tope quedan idénticos) y borra `logo_negocio.png`, la copia reducida del logo que guardaba
  Ajustes. Un `ajustes.json` roto no se toca. El logo original, los resultados, los gastos y la clave no se tocan.
- El navegador vuelve a pedir la hoja de estilos y el programa de la página cada vez (`Cache-Control: no-cache`), para
  no quedarse con los de la versión anterior.

**Cómo se hizo**

- Con el mismo método: un plan corto (apartado 8 de `PLAN.md`) revisado antes de construir, los pasos 23 a 34 de
  `TAREAS.md` con un commit cada uno, todas las pruebas y una revisión corta de seguridad.
- Los resultados de las pruebas y los tiempos están en `PRUEBAS.md`; la revisión, en `REVISION.md`.

**Para la versión siguiente** (siguen pendientes las tres notas de la versión 1)

- Tapar la ruta personal también en los errores que Python escribe por su cuenta al soltar un objeto o al cerrar.
- En Windows, tapar la ruta personal escrita con las barras dobladas o con otras mayúsculas.
- Probar la herramienta en Windows, la primera descarga del modelo mirando la consola y una escena de verdad.

## Versión 1 · 13 de noviembre de 2026

La primera versión, hecha con la ficha 1 de «Construyamos con IA» (guía de Ismagit). Probada en Mac; en Windows, aún
sin probar.

**Qué trae**

- **Subir**: JPG, PNG o WEBP, hasta 20 fotos a la vez y hasta 25 MB cada una. El tipo se comprueba por el contenido del
  archivo. Menos de 500 px de lado corto no se acepta; menos de 1.000 px se acepta con un aviso. Las fotos HEIC tienen
  su mensaje con la solución.
- **Quitar el fondo en el computador**, con rembg y BiRefNet (licencia MIT): el modelo completo («Calidad máxima») en un
  Mac con chip Apple o un PC con tarjeta NVIDIA, y el ligero («Modo rápido») en los demás. Las fotos se procesan en
  cola, con barra de avance. La aceleración se mide una sola vez y se usa lo más rápido.
- **Fondo blanco y medidas** de 8 plataformas: Mercado Libre, Amazon, Shopify, Tiendanube, Instagram, el catálogo de
  Facebook e Instagram, WhatsApp Business y Google Merchant Center. Las medidas están en `plataformas.json`, que se
  puede editar.
- **Escenas con IA** (opcional, con una clave de OpenRouter): 5 escenas preparadas y la tuya, en 1:1, 4:5 o 16:9. El
  costo estimado se ve antes de gastar y hay que confirmarlo; después se ve el costo real. Hay un tope de gasto por
  sesión, cada gasto se anota en `gastos.jsonl` y cada escena lleva la marca IPTC de imagen hecha con IA.
- **Resultados**: una cuadrícula por foto y descarga en ZIP (todo, o una plataforma), con `resumen.csv`.
- **Ajustes**: la clave (se ve solo como «••••» y sus 4 últimos caracteres, con el botón Probar), la marca del negocio,
  la calidad del recorte, el modelo de escenas y el tope de gasto.
- **Solo en este computador**: el servidor escucha en `127.0.0.1` y la página no carga nada de internet.

**Cómo se hizo**

- Por fases: Ficha → Plan → Construcción → Pruebas → Revisión → Demo, con un commit por cada paso de `TAREAS.md`.
- Los resultados de las pruebas y los tiempos están en `PRUEBAS.md`; la revisión de seguridad, en `REVISION.md`.

**Lo que esta versión no hace**

- No abre fotos HEIC (dice cómo convertirlas).
- No se publica en internet: es para un solo computador.
- No vuelve a leer las reglas de cada plataforma: si una cambia, se edita `plataformas.json`.

**Para la versión siguiente** (notas menores del Revisor, que aprobó esta versión; el detalle está en `REVISION.md`)

- Tapar la ruta personal también en los errores que Python escribe por su cuenta al soltar un objeto o al cerrar.
- En Windows, tapar la ruta personal escrita con las barras dobladas o con otras mayúsculas.
- Probar la herramienta en Windows, la primera descarga del modelo mirando la consola y una escena de verdad.
