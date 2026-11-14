# Pruebas

Resultados del 14 de noviembre de 2026, con la versión 1.1, en el computador donde se construyó la herramienta: un Mac
con chip Apple (M5), macOS 26.6, Python 3.12.13 y onnxruntime 1.32.0.

## Resumen

| Batería | Cómo se pasa (desde `herramientas-ia`) | Pruebas | Pasan | Tarda |
|---|---|---|---|---|
| Rápidas (sin internet, recorte simulado) | `uv run --directory estudio-fotos --group pruebas pytest` | 830 | 830 | 1 min 10 s |
| Con el modelo real de recorte | `uv run --directory estudio-fotos --group pruebas pytest -m modelo` | 10 | 10 | 3 min 47 s |
| De punta a punta (Chromium sin ventana) | `uv run --directory estudio-fotos --group pruebas pytest -m e2e` | 6 | 6 | 1 min 54 s |
| **Total** | | **846** | **846** | |

Ninguna falla y ninguna se salta. Son los números de la última pasada de las tres baterías, una detrás de otra, con
todos los cambios de la versión 1.1 hechos y antes de su revisión. La versión 1 terminó con 726 (712, 9 y 5): la 1.1
suma 120 pruebas.

Mientras se hacía esa última pasada, el computador estaba ocupado con otros trabajos pesados, que no son de esta
herramienta: por eso los tiempos del modelo real y de punta a punta salen más altos que en la pasada anterior del mismo
día (3 min 22 s y 1 min 19 s). Las dos pasadas están anotadas abajo. Las rápidas se pasaron una vez más después de
escribir este documento: 830 de 830, en 2 min 04 s, también con el computador ocupado.

## El tiempo por foto en este computador

Con el modelo completo (`birefnet-general`, «Calidad máxima») y el procesador, recortando todas las fotos de
`muestras/`: hoy son las 6 de la guía 1.1, y la prueba usa las que encuentre, sin contar con un número fijo. Se midió
dos veces el mismo día:

| Foto | Pasada anterior | Última pasada | La máscara ocupa |
|---|---|---|---|
| `bolsa_mesa.jpg` | 9,9 s | 11,4 s | 25,8 % |
| `bolso.jpg` | 8,6 s | 10,7 s | 21,5 % |
| `camiseta.jpg` | 8,5 s | 11,8 s | 35,6 % |
| `frasco_vidrio.jpg` | 8,4 s | 10,2 s | 12,1 % |
| `taza_logo.jpg` | 8,2 s | 10,3 s | 18,8 % |
| `zapatilla.jpg` | 8,2 s | 9,0 s | 15,1 % |
| **Media** | **8,6 s** | **10,6 s** | |

- **Cuenta con 9 a 11 s por foto** (el recorte completo: el modelo y la limpieza del color de los bordes). La versión 1
  midió 8,9 s en este mismo computador: el recorte no cambió, y la diferencia entre pasadas es lo ocupado que esté el
  computador.
- Preparar el modelo en memoria, una vez por sesión: 2,2 s en la pasada anterior y 3,1 s en la última.
- En la página (recorrido 1 de punta a punta), las 6 fotos tardaron 104 s en la última pasada, unos 17 s por foto,
  con el computador ocupado. En la pasada anterior, la batería entera tardó 1 min 19 s.

Cada recorte tiene un producto: la máscara ocupa entre el 5 % y el 95 % de la foto en las 6 muestras, también en el
frasco de vidrio (12,1 %).

## La aceleración, medida

La ficha pide medirla y no suponerla. La prueba real (`test_medicion_real_despues_del_primer_lote`) recorta dos
muestras, deja que la herramienta pruebe CoreML en su proceso aparte y recorta una tercera. Con la versión 1.1 se
midió otra vez, en las dos pasadas:

| | Pasada anterior | Última pasada |
|---|---|---|
| Procesador, modelo completo (solo el modelo; la mediana del primer lote) | 8,9 s por foto | 12,8 s por foto |
| CoreML (`MLProgram`) | no terminó de preparar el modelo en 2 minutos: la prueba se cortó a los 120,1 s | lo mismo: cortada a los 120,1 s |
| Con qué se queda | **el procesador** | **el procesador** |
| El lote siguiente (la tercera foto) | funciona: 6,3 s | funciona: 11,6 s |

Es lo mismo que salió las dos veces que se midió con la versión 1, y coincide con lo que avisa la ficha: en un Mac con
chip Apple, CoreML no sirve con BiRefNet. La página lo dice en Ajustes › Calidad del recorte, con el número de cada
medición; en la última: «Medido en este computador: 12,8 s por foto con el procesador. La aceleración tardó más de 2
minutos en preparar el modelo: se usa el procesador.»

En el uso normal esta prueba pasa una sola vez por modelo, después del primer lote y sin parar nada; el resultado
queda en `medicion.json`.

## Qué comprueba cada batería

### Rápidas

| Archivo | Pruebas | Qué comprueba |
|---|---|---|
| `test_estructura.py` | 48 | la carpeta común, `AGENTS.md`, `.gitignore`, versiones fijadas, la firma, la página de inicio, el README y el comando de arranque; la versión 1.1 en todos los sitios, y que no queda el negocio de ejemplo de la versión 1 en ningún archivo |
| `test_config.py` | 13 | las rutas, y que el modo de pruebas va entero (carpeta temporal y simulador) o no arranca |
| `test_plataformas.py` | 19 | `plataformas.json`: las 8 plataformas, sus medidas y que un archivo mal editado se explica |
| `test_subidas.py` | 44 | formato por contenido, tamaño, lado corto, HEIC, foto dañada, bombas de descompresión, nombres sin rutas |
| `test_encuadre.py` | 142 | fondo blanco puro, el porcentaje (±1 %) y el centro (±1 %), medida y peso de cada plataforma, la regla de Amazon |
| `test_recorte.py` | 30 | el recorte, «sin producto», nunca `bria-rmbg`, los dos modelos por su nombre, la carpeta de los modelos |
| `test_cola.py` | 19 | la cola: una foto tras otra, la barra, un fallo no rompe el lote, la descarga del modelo y sus errores |
| `test_medidas.py` | 10 | las medidas en lote, los nombres de archivo, el ZIP y `resumen.csv` |
| `test_clave.py` | 26 | la clave: solo cambia su línea, permisos 600, enmascarada, nunca en una respuesta |
| `test_ajustes.py` | 42 | los tres ajustes (la calidad del recorte, el modelo de las escenas y el tope) y su validación, sin la clave; y la limpieza de lo que dejó la versión 1: la marca del negocio sale de `ajustes.json` y se borra el logo que guardaba Ajustes |
| `test_openrouter.py` | 40 | OpenRouter simulado: éxito, clave no válida, sin saldo (402 y 403), esperas, generación fallida, sin conexión |
| `test_costos.py` | 35 | la estimación, el tope de la sesión (sin llamar a OpenRouter si se supera), lo que queda en la clave, `gastos.jsonl` |
| `test_escenas.py` | 127 | las escenas: el texto, «Fondo liso de un color» y su color (solo con la forma `#RRGGBB`), el formato sin deformar, la marca IPTC, el costo estimado y el real, los errores |
| `test_servidor.py` | 88 | cada ruta del servidor, los errores en español, las cabeceras de seguridad, solo este computador, la subida «por trozos», los datos con otra forma, el color de la escena, las fuentes servidas desde este computador, y que la marca del negocio ya no se recibe ni se guarda |
| `test_privacidad.py` | 9 | después de usar una clave falsa: ningún registro, resultado, respuesta ni página la contiene; la consola, sin la carpeta personal por ningún camino |
| `test_codigo.py` | 24 | el código no usa nada peligroso, solo habla con OpenRouter, y los vigilantes de las pruebas funcionan |
| `test_arranque.py` | 17 | `python -m estudio`: el puerto, «usamos el N», solo `127.0.0.1`, el navegador, un arranque que falla, `trabajo/` vacía al cerrar y la limpieza de la versión 1 al arrancar |
| `test_pagina.py` | 27 | la página (y la de inicio): en español, la firma, nada de internet, los datos se escriben como texto, el selector de color y Ajustes sin marca |
| `test_diseno.py` | 30 | el diseño de Ismagit: las 11 variables de la ficha, los colores solo por variables, las fuentes Geist en este computador (iguales a las de `marca/fuentes/`, y ninguna otra dirección), el logo en la cabecera, un botón principal por zona, el foco, el contraste AA y la firma |
| `test_aceleracion.py` | 40 | la aceleración, con procesos de mentira: falla → procesador; tarda demasiado → procesador; más rápida → se elige (y sus temporales van a `trabajo/`) |

### Con el modelo real

- `test_modelo_real.py` (9): recorta todas las fotos de `muestras/` con el modelo de verdad (una prueba por foto: hoy,
  6), comprueba que cada recorte tiene un producto, que el modelo está en `herramientas-ia/modelos/` y que no apareció
  nada en la carpeta personal.
- `test_aceleracion.py` (1): la medición de la aceleración de arriba.

### De punta a punta

El servidor se arranca como lo arranca el usuario (`python -m estudio`), en otro puerto, con `NO_ABRIR_NAVEGADOR=1`, los
datos en una carpeta temporal, el modelo real de recorte y OpenRouter simulado.

1. Abre la página, sube todas las fotos de `muestras/` (6), espera la barra hasta «6 de 6» y ve un recorte por foto
   (104 s).
2. Elige Mercado Libre, Amazon e Instagram, genera, descarga el ZIP y comprueba sus 25 archivos (6 recortes, 18
   medidas y `resumen.csv`): medidas, blanco puro, porcentaje y peso (3 s).
3. En Ajustes guarda una clave falsa, ve «••••» con sus 4 últimos caracteres, pulsa Probar y ve «Conexión correcta ·
   límite 2,00 $ · usado 0,12 $»; en Ajustes solo están la clave, la calidad del recorte y las escenas, sin marca del
   negocio (1 s).
4. Pide 2 escenas de «Fondo liso de un color», con un color elegido en el selector: ve «2 escenas · costo estimado
   0,08 $ · ¿Generar?» antes de gastar, confirma, ve las 2 escenas marcadas «Para redes y fotos secundarias» y el costo
   real (0,10 $, distinto del estimado a propósito); con el tope superado, la página lo dice y no se gasta (2 s).
5. El diseño de Ismagit, en Fotos, Resultados, Ajustes y los mensajes (vacío, error, aviso, listo, confirmación y
   tope): los colores, los radios y las fuentes que calcula el navegador, Geist y Geist Mono cargadas desde este
   computador, el logo en la cabecera, un solo botón principal por zona, el foco, cada foto sobre su fondo real y la
   página a 360 px de ancho sin desbordar (3 s).
6. En todos los recorridos, cada petición del navegador fue a este computador (también las fuentes), la consola quedó
   sin errores y la salida del servidor no lleva la clave ni rutas personales.

## Después de la revisión de seguridad de la versión 1

La revisión de la versión 1 (`REVISION.md`) dejó los 10 puntos de la ficha en «Bien» y pidió una corrección (C1) y seis sugerencias.
Lo corregido, con sus 17 pruebas nuevas (15 de las correcciones y 2 que exigen que existan `PRUEBAS.md` y
`REVISION.md`):

| Qué | Prueba |
|---|---|
| C1 · La consola no muestra la carpeta personal: ni en la descarga del modelo, ni en los avisos de Python, ni en los registros de las librerías, ni en un error no controlado (sin traza) | `test_privacidad.py`: `test_la_consola_no_muestra_la_carpeta_personal_por_ningun_camino` (un programa aparte que escribe por todos esos caminos), `test_el_registro_de_la_descarga_del_modelo_pasa_por_el_filtro`, `test_la_carpeta_personal_se_tapa_tambien_escrita_con_barras_normales`, `test_el_arranque_protege_la_consola_antes_que_nada`; `test_arranque.py`: `test_si_el_arranque_falla_la_consola_no_muestra_la_traza_ni_la_carpeta_personal` |
| S1 · Una subida «por trozos» se rechaza antes de recibirla (las fotos; en la versión 1, también el logo, que la 1.1 ya no recibe) | `test_servidor.py`: `test_una_subida_que_pesa_demasiado_se_rechaza_antes_de_recibirla` |
| S3 · Si se elige el acelerador, sus temporales van a `trabajo/acelerador` | `test_aceleracion.py`: `test_si_se_elige_el_acelerador_sus_temporales_van_a_la_carpeta_de_trabajo` |
| S4 · La página de inicio tampoco carga nada de internet | `test_pagina.py`: `test_la_pagina_de_inicio_tampoco_carga_nada_de_internet` |
| S5 · Al cerrar (con Ctrl+C o parada desde fuera), `trabajo/` queda vacía y los resultados se quedan | `test_arranque.py`: `test_al_cerrar_no_quedan_fotos_en_la_carpeta_de_trabajo` (2 casos) |
| S6 · Un id de plataforma con un salto de línea no vale; una lista donde va un texto da un 400 con su mensaje, no un 500 | `test_plataformas.py` (2 casos más); `test_servidor.py`: `test_una_lista_donde_va_un_texto_se_rechaza_con_su_mensaje_y_no_con_un_fallo_interno` (4 casos) |

S2 (no hay contraseña local) y el resto de S5 (una sola copia a la vez) quedaron avisados en el `README.md`, sin
cambio en el código.

## Las salvaguardas de las pruebas

- **Nunca se llama a OpenRouter de verdad**: un vigilante corta cualquier llamada del cliente de OpenRouter que no vaya
  a este computador, y el simulador exige la forma exacta de cada petición.
- **Nunca se tocan los archivos reales**: todo va a una carpeta temporal dentro de `estudio-fotos/.pruebas-tmp/`, y otro
  vigilante compara antes y después el `.env`, `ajustes.json`, `gastos.jsonl`, el logo que dejó la versión 1 y
  `salidas/` (sin abrir el `.env`: solo mira su fecha y su tamaño).
- **La clave de las pruebas** se inventa en cada ejecución: no está escrita en ningún archivo.
- **Una batería cada vez**: todas usan la misma carpeta temporal, y una pasada que empieza borra los archivos de otra
  que esté en marcha. Pasó una vez durante la revisión de la versión 1: una prueba de la aceleración falló porque el
  Revisor pasaba pruebas al mismo tiempo; repetida sin nada más en marcha, pasaron todas.

## Los seis controles de la ficha

| Control | Cómo quedó comprobado |
|---|---|
| 1. Recorte limpio | Las pruebas comprueban que hay producto y fondo transparente. Lo fino (pliegues, bordes, asas) se miró a ojo en los recortes de las 6 muestras, sobre un fondo de color fuerte: sin restos del fondo, y el hueco del asa de la taza y el del bolso quedan transparentes. Dos cosas que conviene saber: el frasco de vidrio sale opaco (el vidrio conserva el tono claro del fondo de la foto, no se vuelve transparente) y la camiseta sale con su percha. **Míralo también con tus fotos.** |
| 2. Blanco puro | Automático: todo el fondo de cada archivo, en las 8 plataformas, es 255, 255, 255. |
| 3. Encuadre | Automático: el porcentaje y el centro, con ±1 %. |
| 4. Medidas y peso | Automático: medida, formato y peso de cada plataforma. |
| 5. Escena fiel | **Sin comprobar**: no se generó ninguna escena de verdad (no se gastó dinero). Compruébalo con tu primera escena. |
| 6. Costo honesto | Con OpenRouter simulado: el costo real que se muestra es el que informa OpenRouter, y la siguiente estimación ya lo usa. **Con OpenRouter de verdad, sin comprobar.** |

## Lo que no se probó

- **OpenRouter de verdad**: ninguna prueba lo llama y la construcción no gastó nada. Las reglas de la ficha (la forma
  de la petición, los códigos de error) están comprobadas contra el simulador, no contra el servicio.
- **Windows y Linux**: todo se probó en Mac. El README dice «Para Mac y Windows» porque así lo pide la ficha 1.1,
  pero en este computador no se pudo probar Windows.
- **Una tarjeta NVIDIA**: ese camino solo tiene pruebas con piezas de mentira.
- **El modelo ligero** (`birefnet-general-lite`): no se descargó en este computador (aquí toca el completo). Su nombre
  está comprobado contra la lista de rembg, pero no se recortó ninguna foto con él.
- **La primera descarga del modelo, mirando la consola**: el modelo ya estaba descargado. Que la línea de la descarga
  sale sin la carpeta personal está comprobado escribiéndola por el mismo registro que usa la descarga, no
  descargando de verdad.
- **Los temporales del acelerador con CoreML de verdad**: aquí la medición deja el procesador, así que ese camino
  solo tiene la prueba de que la carpeta temporal se cambia a `trabajo/acelerador`.
