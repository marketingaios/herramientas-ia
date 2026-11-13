# Pruebas

Resultados del 13 de noviembre de 2026, en el computador donde se construyó la herramienta: un Mac con chip Apple (M5),
macOS 26.6, Python 3.12.13 y onnxruntime 1.32.0.

## Resumen

| Batería | Cómo se pasa (desde `herramientas-ia`) | Pruebas | Pasan | Tarda |
|---|---|---|---|---|
| Rápidas (sin internet, recorte simulado) | `uv run --directory estudio-fotos --group pruebas pytest` | 695 | 695 | 58 s |
| Con el modelo real de recorte | `uv run --directory estudio-fotos --group pruebas pytest -m modelo` | 9 | 9 | 3 min 12 s |
| De punta a punta (Chromium sin ventana) | `uv run --directory estudio-fotos --group pruebas pytest -m e2e` | 5 | 5 | 49 s |
| **Total** | | **709** | **709** | |

Ninguna falla y ninguna se salta.

## El tiempo por foto en este computador

Con el modelo completo (`birefnet-general`, «Calidad máxima») y el procesador, recortando las 5 fotos de `muestras/`:

| Foto | Segundos | La máscara ocupa |
|---|---|---|
| `bolsa_500g_cocina.jpg` | 9,5 | 29,4 % |
| `bolsa_cenital.jpg` | 8,6 | 35,4 % |
| `bolsa_mesa.jpg` | 9,0 | 25,8 % |
| `caja_suscripcion.jpg` | 8,7 | 46,6 % |
| `taza_logo.jpg` | 8,6 | 18,8 % |

- **Media: 8,9 s por foto** (el recorte completo: el modelo y la limpieza del color de los bordes).
- Preparar el modelo en memoria, una vez por sesión: 2,2 s.
- En la página (recorrido 1 de punta a punta), las 5 fotos tardaron unos 43 s en total: lo mismo, 8 o 9 s por foto.
- En otras pasadas del mismo día el recorte tardó entre 6 y 7,5 s por foto: cuenta con 6 a 9 s.

Cada recorte tiene un producto: la máscara ocupa entre el 5 % y el 95 % de la foto en las 5 muestras.

## La aceleración, medida

La ficha pide medirla y no suponerla. La prueba real (`test_medicion_real_despues_del_primer_lote`) recorta dos
muestras, deja que la herramienta pruebe CoreML en su proceso aparte y recorta una tercera:

| | Resultado |
|---|---|
| Procesador, modelo completo | 8,1 s por foto (solo el modelo; la mediana del primer lote) |
| CoreML (`MLProgram`) | no terminó de preparar el modelo en 2 minutos: la prueba se cortó a los 120,1 s |
| Con qué se queda | **el procesador** |
| El lote siguiente | funciona: la tercera foto se recortó en 6,7 s |

Se midió dos veces el mismo día y salió lo mismo las dos. Coincide con lo que avisa la ficha: en un Mac con chip
Apple, CoreML no sirve con BiRefNet. La página lo dice en Ajustes › Calidad del recorte: «Medido en este computador:
8,1 s por foto con el procesador. La aceleración tardó más de 2 minutos en preparar el modelo: se usa el procesador.»

En el uso normal esta prueba pasa una sola vez por modelo, después del primer lote y sin parar nada; el resultado
queda en `medicion.json`.

## Qué comprueba cada batería

### Rápidas

| Archivo | Pruebas | Qué comprueba |
|---|---|---|
| `test_estructura.py` | 38 | la carpeta común, `AGENTS.md`, `.gitignore`, versiones fijadas, la firma, la página de inicio, el README y el comando de arranque |
| `test_config.py` | 13 | las rutas, y que el modo de pruebas va entero (carpeta temporal y simulador) o no arranca |
| `test_plataformas.py` | 17 | `plataformas.json`: las 8 plataformas, sus medidas y que un archivo mal editado se explica |
| `test_subidas.py` | 44 | formato por contenido, tamaño, lado corto, HEIC, foto dañada, bombas de descompresión, nombres sin rutas |
| `test_encuadre.py` | 142 | fondo blanco puro, el porcentaje (±1 %) y el centro (±1 %), medida y peso de cada plataforma, la regla de Amazon |
| `test_recorte.py` | 30 | el recorte, «sin producto», nunca `bria-rmbg`, los dos modelos por su nombre, la carpeta de los modelos |
| `test_cola.py` | 19 | la cola: una foto tras otra, la barra, un fallo no rompe el lote, la descarga del modelo y sus errores |
| `test_medidas.py` | 10 | las medidas en lote, los nombres de archivo, el ZIP y `resumen.csv` |
| `test_clave.py` | 26 | la clave: solo cambia su línea, permisos 600, enmascarada, nunca en una respuesta |
| `test_ajustes.py` | 37 | los ajustes y su validación (colores, textos, logo), sin la clave |
| `test_openrouter.py` | 40 | OpenRouter simulado: éxito, clave no válida, sin saldo (402 y 403), esperas, generación fallida, sin conexión |
| `test_costos.py` | 35 | la estimación, el tope de la sesión (sin llamar a OpenRouter si se supera), lo que queda en la clave, `gastos.jsonl` |
| `test_escenas.py` | 67 | las escenas: el texto, el formato sin deformar, la marca IPTC, el costo estimado y el real, los errores |
| `test_servidor.py` | 69 | cada ruta del servidor, los errores en español, las cabeceras de seguridad, solo este computador |
| `test_privacidad.py` | 5 | después de usar una clave falsa: ningún registro, resultado, respuesta ni página la contiene |
| `test_codigo.py` | 24 | el código no usa nada peligroso, solo habla con OpenRouter, y los vigilantes de las pruebas funcionan |
| `test_arranque.py` | 13 | `python -m estudio`: el puerto, «usamos el N», solo `127.0.0.1`, el navegador |
| `test_pagina.py` | 27 | la página: en español, la firma, nada de internet, los datos se escriben como texto |
| `test_aceleracion.py` | 39 | la aceleración, con procesos de mentira: falla → procesador; tarda demasiado → procesador; más rápida → se elige |

### Con el modelo real

- `test_modelo_real.py` (8): recorta las 5 muestras con el modelo de verdad, comprueba que cada recorte tiene un
  producto, que el modelo está en `herramientas-ia/modelos/` y que no apareció nada en la carpeta personal.
- `test_aceleracion.py` (1): la medición de la aceleración de arriba.

### De punta a punta

El servidor se arranca como lo arranca el usuario (`python -m estudio`), en otro puerto, con `NO_ABRIR_NAVEGADOR=1`, los
datos en una carpeta temporal, el modelo real de recorte y OpenRouter simulado.

1. Abre la página, sube las 5 fotos de `muestras/`, espera la barra hasta «5 de 5» y ve los 5 recortes (43 s).
2. Elige Mercado Libre, Amazon e Instagram, genera, descarga el ZIP y comprueba sus 21 archivos (5 recortes, 15
   medidas y `resumen.csv`): medidas, blanco puro, porcentaje y peso (2 s).
3. En Ajustes guarda una clave falsa, ve «••••» con sus 4 últimos caracteres, pulsa Probar y ve «Conexión correcta ·
   límite 2,00 $ · usado 0,12 $»; pone la marca del negocio y la página cambia de colores (1 s).
4. Pide 2 escenas: ve «2 escenas · costo estimado 0,08 $ · ¿Generar?» antes de gastar, confirma, ve las 2 escenas
   marcadas «Para redes y fotos secundarias» y el costo real (0,10 $, distinto del estimado a propósito); con el tope
   superado, la página lo dice y no se gasta (2 s).
5. En todos los recorridos, cada petición del navegador fue a este computador, la consola quedó sin errores y la
   salida del servidor no lleva la clave ni rutas personales.

## Las salvaguardas de las pruebas

- **Nunca se llama a OpenRouter de verdad**: un vigilante corta cualquier llamada del cliente de OpenRouter que no vaya
  a este computador, y el simulador exige la forma exacta de cada petición.
- **Nunca se tocan los archivos reales**: todo va a una carpeta temporal dentro de `estudio-fotos/.pruebas-tmp/`, y otro
  vigilante compara antes y después el `.env`, `ajustes.json`, `gastos.jsonl`, el logo y `salidas/` (sin abrir el
  `.env`: solo mira su fecha y su tamaño).
- **La clave de las pruebas** se inventa en cada ejecución: no está escrita en ningún archivo.

## Los seis controles de la ficha

| Control | Cómo quedó comprobado |
|---|---|
| 1. Recorte limpio | Las pruebas comprueban que hay producto y fondo transparente. Lo fino (pliegues, bordes) se miró a ojo en las capturas de las 5 muestras: sin restos del fondo. **Míralo también con tus fotos.** |
| 2. Blanco puro | Automático: todo el fondo de cada archivo, en las 8 plataformas, es 255, 255, 255. |
| 3. Encuadre | Automático: el porcentaje y el centro, con ±1 %. |
| 4. Medidas y peso | Automático: medida, formato y peso de cada plataforma. |
| 5. Escena fiel | **Sin comprobar**: no se generó ninguna escena de verdad (no se gastó dinero). Compruébalo con tu primera escena. |
| 6. Costo honesto | Con OpenRouter simulado: el costo real que se muestra es el que informa OpenRouter, y la siguiente estimación ya lo usa. **Con OpenRouter de verdad, sin comprobar.** |

## Lo que no se probó

- **OpenRouter de verdad**: ninguna prueba lo llama y la construcción no gastó nada. Las reglas de la ficha (la forma
  de la petición, los códigos de error) están comprobadas contra el simulador, no contra el servicio.
- **Windows y Linux**: todo se probó en Mac.
- **Una tarjeta NVIDIA**: ese camino solo tiene pruebas con piezas de mentira.
- **El modelo ligero** (`birefnet-general-lite`): no se descargó en este computador (aquí toca el completo). Su nombre
  está comprobado contra la lista de rembg, pero no se recortó ninguna foto con él.
