# herramientas-ia

Esta carpeta guarda las herramientas del negocio construidas con las fichas de «Construyamos con IA» (guía de
Ismagit). Cada herramienta vive en su propia carpeta y funciona solo en este computador.

## Reglas fijas

- **Claves**: nunca leas, muestres, copies ni busques el contenido de `.env`, y no crees ningún `.env` (ni de ejemplo).
  La clave la escribe solo la página de Ajustes de cada herramienta. Nunca va en el código, los registros, los errores,
  las respuestas ni las pruebas.
- **Pruebas**: usan simuladores y una carpeta temporal. Nunca llaman a OpenRouter de verdad ni tocan el `.env` real,
  `ajustes.json`, `salidas/` ni `gastos.jsonl`.
- **Solo en este computador**: los servidores escuchan solo en `127.0.0.1`; nada de `0.0.0.0`, túneles ni publicación.
  Las páginas no cargan nada de internet.
- **Gasto**: una sola clave (OpenRouter). Antes de gastar, la página muestra el costo estimado y pide confirmar; después
  muestra el costo real. Hay un tope de gasto por sesión.
- **Para quien la usa**: todo en español, trabajos en lote con barra de avance, errores que dicen qué pasó y qué hacer.
  Sin datos personales en páginas ni registros. La firma de Ismagit va en el pie de cada página, nunca en las fotos.
- **No borres ni cambies lo que ya existe**: solo añade. Trabaja solo dentro de esta carpeta.

## Método

Se trabaja por fases: Ficha → Plan → Construcción → Pruebas → Revisión → Demo.

- El plan (`PLAN.md`) y los pasos (`TAREAS.md`) se escriben antes de programar, y un Revisor los compara con la ficha.
- Un paso a la vez, cada uno con su prueba y su commit en español.
- Antes de entregar, el Revisor (un subagente con el contexto limpio, que no escribe código) hace la revisión de
  seguridad y escribe `REVISION.md`.
- No se hacen preguntas: se elige lo más simple y se anota en «Decisiones» del plan. Se pide permiso solo para instalar
  algo fuera de esta carpeta o para gastar dinero.

## Herramientas

| Herramienta | Carpeta | Versión | Dirección | Cómo abrirla (Mac, Linux y Windows) |
|---|---|---|---|---|
| Estudio de fotos de producto | `estudio-fotos/` | 1 | http://127.0.0.1:8601 | `uv run --directory estudio-fotos python -m estudio` |

El comando es el mismo en Mac, Linux y Windows, y se escribe desde esta carpeta (`herramientas-ia`). Si el puerto está
ocupado, la herramienta usa el siguiente libre y lo dice al arrancar.

## Cuando el usuario pide «Abre …»

1. Busca la herramienta en la tabla.
2. Arráncala **en segundo plano** con su comando, desde esta carpeta.
3. Espera a que responda: el arranque escribe una línea con la dirección («Estudio de fotos abierto en
   http://127.0.0.1:8601») y abre el navegador.
4. Da la dirección al usuario.

Para arrancar sin abrir el navegador (pruebas automáticas o un servidor), define `NO_ABRIR_NAVEGADOR=1`.

## Carpetas comunes

- `estilo/`: `estilo.css` (los colores de la marca como variables) y `firma.html` (la firma de Ismagit que cada página lleva en su pie).
- `marca/`: los logos de Ismagit y el de Café 2600, el negocio de ejemplo.
- `muestras/`: fotos de ejemplo de Café 2600, hechas con IA.
- `modelos/`: los modelos descargados, compartidos por todas las herramientas (fuera de git).
- `inicio/index.html`: la página de inicio, con la lista de herramientas.
