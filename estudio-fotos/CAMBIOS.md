# Cambios

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
