# AI tools · Construyamos con IA

[Leer en español](README.md)

Marketing tools that run on your own computer, built by AI agents in the «Construyamos con IA» («Let's build with AI»)
series of the [CheloAI](https://www.youtube.com/@CheloAI) YouTube channel. Each tool lives in its own folder and ships
with the spec it was built from, so you can use it as is or have your own agent build it from scratch. The tools, their
pages and their docs are in Spanish.

The video (in Spanish), with the tool at work and how the agents built it:
[Construyamos con IA · el estudio de fotos](https://youtu.be/NRCYtXvr86s).

## The tools

| Tool | What it does | Folder |
|---|---|---|
| Estudio de fotos de producto (product photo studio) | Removes the background on your computer, places the product on pure white at each online store's size and, optionally, creates AI scenes | [`estudio-fotos/`](estudio-fotos/) |

## Step by step

### Use it directly

1. **Download** this repository: green «Code» button › «Download ZIP», and unzip it. The folder is called
   `herramientas-ia-main`: keep that name or rename it `herramientas-ia`, the tool works with any name.
2. **Put it** in your home folder. On Windows, outside OneDrive: syncing locks files and would upload the cut-out model
   to the cloud.
3. **Install [uv](https://docs.astral.sh/uv/)** once: it sets up Python and the libraries.
   - On a Mac, open the Terminal app, paste this line and press Enter:
     `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - On Windows, open PowerShell, paste this line and press Enter:
     `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

   Then close that window and open a new one, so the `uv` command is found.
4. **Open a terminal in the folder.** On a Mac, type `cd ` (with the space), drag the folder onto the window and press
   Enter. On Windows 11, open the folder in File Explorer, right-click an empty spot and choose «Open in Terminal» (on
   Windows 10, Shift + right-click › «Open PowerShell window here»).
5. **Open the studio** with this command:

   ```
   uv run --directory estudio-fotos python -m estudio
   ```

   The first time takes a few minutes: it installs the libraries and, with the first cut-out, downloads the model (up
   to 1 GB). Your browser opens at http://127.0.0.1:8601. To close it, `Ctrl` + `C` in that window.

If you use an AI agent (Claude Code, Codex or OpenCode), open it **inside this folder** and tell it «Abre el estudio de
fotos»: it does step 5 for you. Everything else is in [`estudio-fotos/README.md`](estudio-fotos/README.md) (Spanish).

### Build it from scratch

1. Download the ZIP as above and create a new folder called `herramientas-ia` in your home folder (on Windows, outside
   OneDrive).
2. Copy only three things from the ZIP into it: the [`instrucciones.md`](instrucciones.md) file and the `muestras`
   (sample photos) and `marca` (logo and fonts) folders. Nothing else: your agent builds the rest.
3. Open your agent (Claude Code, Codex or OpenCode) **in that folder** and type «Lee instrucciones.md y construye la
   herramienta». It works in phases and takes a few hours; it only asks permission to install something outside the
   folder or to spend money.
4. When it is done, type «Abre el estudio de fotos».

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

[MIT](LICENSE). The Ismagit name and logo (`marca/`) are not covered by the license ([NOTICE](NOTICE)). The Geist fonts have their own
license (OFL).

A project by [Ismagit](https://ismagit.com).
