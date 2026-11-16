# Herramientas IA · Construyamos con IA

[Read in English](README.en.md)

Herramientas de marketing que funcionan en tu computador, construidas por agentes de IA en la serie «Construyamos con
IA» del canal [CheloAI](https://www.youtube.com/@CheloAI). Cada herramienta vive en su propia carpeta y trae la ficha
con la que se construyó, para que la uses tal cual o la construyas tú desde cero con tu agente.

El vídeo, con la herramienta funcionando y cómo la construyeron los agentes:
[Construyamos con IA · el estudio de fotos](https://youtu.be/NRCYtXvr86s).

## Las herramientas

| Herramienta | Qué hace | Carpeta |
|---|---|---|
| Estudio de fotos de producto | Quita el fondo en tu computador, pone el producto sobre blanco en las medidas de cada tienda online y, si quieres, crea escenas con IA | [`estudio-fotos/`](estudio-fotos/) |

## Paso a paso

### Usarla directamente

1. **Descarga** este repositorio: botón verde «Code» › «Download ZIP», y descomprímelo. La carpeta se llama
   `herramientas-ia-main`: puedes dejarla así o llamarla `herramientas-ia`, la herramienta funciona con cualquier nombre.
2. **Ponla** en tu carpeta personal. En Windows, fuera de OneDrive: la sincronización bloquea archivos y subiría el
   modelo de recorte a la nube.
3. **Instala [uv](https://docs.astral.sh/uv/)** una sola vez: es el programa que prepara Python y las librerías.
   - En Mac, abre la app Terminal, pega esta línea y pulsa Enter:
     `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - En Windows, abre PowerShell, pega esta línea y pulsa Enter:
     `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

   Después cierra esa ventana y abre otra, para que reconozca el comando `uv`.
4. **Abre la terminal en la carpeta.** En Mac, escribe `cd ` (con el espacio), arrastra la carpeta a la ventana y pulsa
   Enter. En Windows 11, abre la carpeta en el Explorador, haz clic derecho en un espacio vacío y elige «Abrir en
   Terminal» (en Windows 10, Mayúsculas + clic derecho › «Abrir la ventana de PowerShell aquí»).
5. **Abre el estudio** con este comando:

   ```
   uv run --directory estudio-fotos python -m estudio
   ```

   La primera vez tarda unos minutos: instala las librerías y, con el primer recorte, descarga el modelo (hasta 1 GB).
   Se abre el navegador en http://127.0.0.1:8601. Para cerrarlo, `Ctrl` + `C` en esa ventana.

Si usas un agente de IA (Claude Code, Codex u OpenCode), ábrelo **dentro de esta carpeta** y dile «Abre el estudio de
fotos»: el paso 5 lo hace él. Todo lo demás, en [`estudio-fotos/README.md`](estudio-fotos/README.md).

### Construirla desde cero

1. Descarga el ZIP como arriba y crea en tu carpeta personal una carpeta nueva llamada `herramientas-ia` (en Windows,
   fuera de OneDrive).
2. Copia en ella solo tres cosas del ZIP: el archivo [`instrucciones.md`](instrucciones.md) y las carpetas `muestras`
   (las fotos de ejemplo) y `marca` (el logo y las fuentes). Nada más: el resto lo construye tu agente.
3. Abre tu agente (Claude Code, Codex u OpenCode) **en esa carpeta** y escribe «Lee instrucciones.md y construye la
   herramienta». Trabaja por fases y tarda unas horas; solo te pide permiso para instalar algo fuera de la carpeta o
   para gastar dinero.
4. Cuando termine, escribe «Abre el estudio de fotos».

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

[MIT](LICENSE). El nombre y el logo de Ismagit (`marca/`) no están incluidos en la licencia ([NOTICE](NOTICE)). Las fuentes Geist tienen
su propia licencia (OFL).

Un proyecto de [Ismagit](https://ismagit.com).
