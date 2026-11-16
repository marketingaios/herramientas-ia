# Herramientas IA · Construyamos con IA

[Read in English](README.en.md)

Herramientas de marketing que funcionan en tu computador, construidas por agentes de IA en la serie «Construyamos con
IA» del canal [CheloAI](https://www.youtube.com/@CheloAI). Cada herramienta vive en su propia carpeta y trae la ficha
con la que se construyó, para que la uses tal cual o la construyas tú desde cero con tu agente.

## Las herramientas

| Herramienta | Qué hace | Carpeta |
|---|---|---|
| Estudio de fotos de producto | Quita el fondo en tu computador, pone el producto sobre blanco en las medidas de cada tienda online y, si quieres, crea escenas con IA | [`estudio-fotos/`](estudio-fotos/) |

## Dos caminos

**Usarla directamente.** Descarga este repositorio (botón «Code» › «Download ZIP», o `git clone`), instala
[uv](https://docs.astral.sh/uv/) y, desde la carpeta `herramientas-ia`:

```
uv run --directory estudio-fotos python -m estudio
```

O dile a tu agente de IA «Abre el estudio de fotos». El resto, en [`estudio-fotos/README.md`](estudio-fotos/README.md).

**Construirla desde cero.** La ficha [`instrucciones.md`](instrucciones.md) es todo lo que tu agente (Claude Code,
Codex u OpenCode) necesita: crea una carpeta `herramientas-ia` con la ficha y las carpetas `muestras` y `marca`, abre tu
agente ahí y escribe «Lee instrucciones.md y construye la herramienta».

## Cómo se construyó

Con método, no improvisando: Ficha → Plan → Construcción → Pruebas → Revisión → Demo. El plan (`PLAN.md`), los pasos
(`TAREAS.md`), las pruebas (`PRUEBAS.md`) y la revisión de seguridad (`REVISION.md`) están en la carpeta de cada
herramienta, y cada paso tiene su commit.

## Qué necesitas

- Mac o Windows, con unos 3 GB libres para el modelo de recorte y las librerías. Probado en Mac; en Windows sigue la
  sección «Si usas Windows» de la ficha.
- Solo para las escenas con IA: una clave de [OpenRouter](https://openrouter.ai) con un tope de gasto, que se pone en
  la página de Ajustes y nunca sale de tu computador.

Las fotos de `muestras/` son fotos de ejemplo hechas con IA.

## Licencia

[MIT](LICENSE). El nombre y el logo de Ismagit (`marca/`) no están incluidos en la licencia. Las fuentes Geist tienen
su propia licencia (OFL).

Un proyecto de [Ismagit](https://ismagit.com).
