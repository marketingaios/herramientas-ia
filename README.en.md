# AI tools · Construyamos con IA

[Leer en español](README.md)

Marketing tools that run on your own computer, built by AI agents in the «Construyamos con IA» («Let's build with AI»)
series of the [CheloAI](https://www.youtube.com/@CheloAI) YouTube channel. Each tool lives in its own folder and ships
with the spec it was built from, so you can use it as is or have your own agent build it from scratch. The tools, their
pages and their docs are in Spanish.

## The tools

| Tool | What it does | Folder |
|---|---|---|
| Estudio de fotos de producto (product photo studio) | Removes the background on your computer, places the product on pure white at each online store's size and, optionally, creates AI scenes | [`estudio-fotos/`](estudio-fotos/) |

## Two ways

**Use it directly.** Download this repository («Code» › «Download ZIP», or `git clone`), install
[uv](https://docs.astral.sh/uv/) and, from the `herramientas-ia` folder:

```
uv run --directory estudio-fotos python -m estudio
```

Or tell your AI agent «Abre el estudio de fotos». More in [`estudio-fotos/README.md`](estudio-fotos/README.md).

**Build it from scratch.** The spec [`instrucciones.md`](instrucciones.md) is all your agent (Claude Code, Codex or
OpenCode) needs: create a `herramientas-ia` folder with the spec and the `muestras` and `marca` folders, open your agent
there and type «Lee instrucciones.md y construye la herramienta».

## How it was built

With a method, not by improvising: Spec → Plan → Build → Tests → Review → Demo. The plan (`PLAN.md`), the steps
(`TAREAS.md`), the tests (`PRUEBAS.md`) and the security review (`REVISION.md`) are in each tool's folder, and every
step has its own commit.

## Requirements

- macOS or Windows, with about 3 GB free for the cut-out model and the libraries. Tested on macOS; on Windows follow
  the «Si usas Windows» section of the spec.
- Only for AI scenes: an [OpenRouter](https://openrouter.ai) key with a spending limit, entered on the Settings page; it
  never leaves your computer.

The photos in `muestras/` are sample photos made with AI.

## License

[MIT](LICENSE). The Ismagit name and logo (`marca/`) are not covered by the license. The Geist fonts have their own
license (OFL).

A project by [Ismagit](https://ismagit.com).
