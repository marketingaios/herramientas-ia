/* Estudio de fotos de producto: la página.
   Sin librerías y sin nada de internet. Todo lo que viene del usuario o del servidor (nombres de archivo, la escena
   que escribe el usuario, los mensajes) se escribe siempre como texto (textContent), nunca como HTML. */
"use strict";

(() => {
  const MAX_FOTOS = 20;
  const MENSAJE_DEMASIADAS = "Se pueden subir hasta 20 fotos a la vez.";
  const MENSAJE_SIN_RESPUESTA = "La herramienta no responde. Comprueba que sigue abierta y vuelve a intentarlo.";

  const $ = (id) => document.getElementById(id);

  /** Crea un elemento con su clase y su texto (siempre como texto). */
  function crear(etiqueta, clase, texto) {
    const elemento = document.createElement(etiqueta);
    if (clase) elemento.className = clase;
    if (texto !== undefined && texto !== null) elemento.textContent = texto;
    return elemento;
  }

  function mostrar(elemento, visible) {
    elemento.hidden = !visible;
  }

  /** Vacía una lista y la llena con notas (avisos o errores). */
  function pintarNotas(lista, notas) {
    lista.replaceChildren(...notas.map((nota) => crear("li", `nota ${nota.clase}`, nota.texto)));
    mostrar(lista, notas.length > 0);
  }

  // --- Hablar con el servidor (siempre el de este computador) -----------------------------------------------------

  async function pedir(metodo, ruta, cuerpo) {
    const opciones = { method: metodo, headers: {} };
    if (cuerpo instanceof FormData) {
      opciones.body = cuerpo;
    } else if (cuerpo !== undefined) {
      opciones.headers["Content-Type"] = "application/json";
      opciones.body = JSON.stringify(cuerpo);
    }
    let respuesta;
    try {
      respuesta = await fetch(ruta, opciones);
    } catch (error) {
      throw new Error(MENSAJE_SIN_RESPUESTA);
    }
    let datos = null;
    try {
      datos = await respuesta.json();
    } catch (error) {
      datos = null;
    }
    if (!respuesta.ok) {
      throw new Error((datos && datos.error) || "Algo falló. Inténtalo otra vez.");
    }
    return datos;
  }

  // --- El estado: se consulta cada poco y se vuelve a pintar ------------------------------------------------------

  let estado = null;
  let opciones = null; // plataformas, escenas, formatos y modelos: se piden una vez
  let temporizador = null;
  const pintores = [];
  const alCambiarSeleccion = []; // lo que hay que repintar cuando se marca o desmarca una foto

  function hayTrabajo() {
    if (!estado) return false;
    const trabajando = Object.values(estado.trabajos).some((trabajo) => trabajo.estado === "trabajando");
    return trabajando || ["descargando", "preparando"].includes(estado.modelo.estado);
  }

  async function refrescar() {
    clearTimeout(temporizador);
    try {
      estado = await pedir("GET", "/api/estado");
      mostrar($("sin-respuesta"), false);
      for (const pintar of pintores) pintar(estado);
    } catch (error) {
      mostrar($("sin-respuesta"), true);
    }
    temporizador = setTimeout(refrescar, hayTrabajo() ? 700 : 2500);
  }

  // --- Las tres zonas ---------------------------------------------------------------------------------------------

  const ZONAS = ["fotos", "resultados", "ajustes"];

  function irA(zona) {
    if (!ZONAS.includes(zona)) zona = "fotos";
    for (const nombre of ZONAS) mostrar($(`zona-${nombre}`), nombre === zona);
    for (const boton of document.querySelectorAll(".zona-boton")) {
      if (boton.dataset.zona === zona) boton.setAttribute("aria-current", "page");
      else boton.removeAttribute("aria-current");
    }
    if (location.hash !== `#${zona}`) history.replaceState(null, "", `#${zona}`);
  }

  for (const boton of document.querySelectorAll(".zona-boton")) {
    boton.addEventListener("click", () => irA(boton.dataset.zona));
  }
  window.addEventListener("hashchange", () => irA(location.hash.slice(1)));

  // --- Los avisos generales ---------------------------------------------------------------------------------------
  // La página lleva siempre el diseño de Ismagit: nada de lo que llega del servidor cambia sus colores ni su título.

  pintores.push((actual) => {
    $("aviso-puerto").textContent = actual.aviso_puerto || "";
    mostrar($("aviso-puerto"), Boolean(actual.aviso_puerto));
  });

  // --- Zona Fotos: subir ------------------------------------------------------------------------------------------

  const soltar = $("soltar");
  const elegir = $("elegir-fotos");

  async function subir(archivos) {
    archivos = Array.from(archivos || []);
    if (!archivos.length) return;
    if (archivos.length > MAX_FOTOS) {
      pintarNotas($("avisos-subida"), [{ clase: "nota-error", texto: MENSAJE_DEMASIADAS }]);
      return;
    }
    const formulario = new FormData();
    for (const archivo of archivos) formulario.append("fotos", archivo, archivo.name);

    const subiendo = $("subiendo");
    subiendo.textContent = archivos.length === 1 ? "Subiendo 1 foto…" : `Subiendo ${archivos.length} fotos…`;
    mostrar(subiendo, true);
    pintarNotas($("avisos-subida"), []);
    try {
      const respuesta = await pedir("POST", "/api/fotos", formulario);
      const notas = [];
      for (const foto of respuesta.fotos) {
        if (!foto.aceptada) notas.push({ clase: "nota-error", texto: `${foto.archivo}: ${foto.error}` });
        else if (foto.aviso) notas.push({ clase: "nota-aviso", texto: `${foto.archivo}: ${foto.aviso}` });
      }
      pintarNotas($("avisos-subida"), notas);
    } catch (error) {
      pintarNotas($("avisos-subida"), [{ clase: "nota-error", texto: error.message }]);
    } finally {
      mostrar(subiendo, false);
      elegir.value = "";
      refrescar();
    }
  }

  elegir.addEventListener("change", () => subir(elegir.files));

  for (const evento of ["dragenter", "dragover"]) {
    soltar.addEventListener(evento, (e) => {
      e.preventDefault();
      soltar.classList.add("encima");
    });
  }
  for (const evento of ["dragleave", "drop"]) {
    soltar.addEventListener(evento, (e) => {
      e.preventDefault();
      soltar.classList.remove("encima");
    });
  }
  soltar.addEventListener("drop", (e) => subir(e.dataTransfer ? e.dataTransfer.files : []));
  // Si una foto cae fuera de la zona, el navegador no debe abrirla en lugar de la página.
  for (const evento of ["dragover", "drop"]) window.addEventListener(evento, (e) => e.preventDefault());

  // --- Zona Fotos: el modelo de recorte y la barra de avance ------------------------------------------------------

  $("reintentar-modelo").addEventListener("click", async () => {
    try {
      await pedir("POST", "/api/modelo/reintentar");
    } finally {
      refrescar();
    }
  });

  pintores.push((actual) => {
    const modelo = actual.modelo;
    $("chip-modelo").textContent = modelo.etiqueta;
    mostrar($("chip-modelo"), Boolean(modelo.etiqueta));
    $("nota-modelo").textContent = modelo.nota || "";
    mostrar($("nota-modelo"), Boolean(modelo.nota));
    // La aceleración se mide, no se supone: en Ajustes se dice qué salió (o que se está midiendo).
    $("medicion-modelo").textContent = modelo.medicion || "";
    mostrar($("medicion-modelo"), Boolean(modelo.medicion));

    const caja = $("estado-modelo");
    const ocupado = ["descargando", "preparando", "error"].includes(modelo.estado);
    mostrar(caja, ocupado);
    if (ocupado) {
      let texto = modelo.mensaje || "";
      if (modelo.estado === "descargando" && modelo.total_mb) {
        texto += ` · ${modelo.descargado_mb} de ${modelo.total_mb} MB`;
        $("barra-modelo").style.width = `${Math.min(100, (modelo.descargado_mb / modelo.total_mb) * 100)}%`;
      }
      $("texto-modelo").textContent = texto;
      caja.className = modelo.estado === "error" ? "nota nota-error" : "nota";
      mostrar($("barra-modelo-caja"), modelo.estado === "descargando");
      mostrar($("reintentar-modelo"), modelo.estado === "error");
    }
  });

  /** Pinta la barra y el texto de un trabajo en lote: «3 de 5 · foto_3.jpg · 4,2 s». */
  function pintarAvance(trabajo, ids) {
    const visible = trabajo.estado !== "inactivo";
    mostrar($(ids.caja), visible);
    if (!visible) return;
    const hechos = trabajo.estado === "terminado" ? trabajo.total : trabajo.hechos;
    const porcentaje = trabajo.total ? Math.round((hechos / trabajo.total) * 100) : 0;
    $(ids.barra).style.width = `${trabajo.estado === "terminado" ? 100 : porcentaje}%`;
    $(ids.barra).parentElement.setAttribute("aria-valuenow", String(porcentaje));
    $(ids.texto).textContent = trabajo.texto;
    if (ids.errores) {
      pintarNotas(
        $(ids.errores),
        trabajo.errores.map((fallo) => ({ clase: "nota-error", texto: `${fallo.archivo}: ${fallo.mensaje}` })),
      );
    }
  }

  pintores.push((actual) => {
    pintarAvance(actual.trabajos.recorte, { caja: "avance-recorte", barra: "barra-recorte", texto: "texto-recorte" });
  });

  // --- Zona Fotos: cada foto, con su antes y después --------------------------------------------------------------

  const tarjetas = new Map(); // id de la foto → lo que hay pintado
  const sinMarcar = new Set(); // las fotos que el usuario desmarcó: no entran en las medidas ni en las escenas

  /** Las fotos ya recortadas que siguen marcadas. */
  function fotosElegidas() {
    if (!estado) return [];
    return estado.fotos.filter((foto) => foto.estado === "lista" && !sinMarcar.has(foto.id)).map((foto) => foto.id);
  }

  const ESTADOS = { en_cola: "En cola", recortando: "Recortando…" };

  function crearTarjeta(foto) {
    const elemento = crear("li", "foto");
    elemento.dataset.id = foto.id;

    const comparador = crear("div", "comparador sin-recorte");
    const despues = crear("img", "despues");
    despues.alt = `${foto.archivo}: después, sin fondo`;
    despues.hidden = true;
    const antes = crear("img", "antes");
    antes.alt = `${foto.archivo}: antes`;
    antes.src = `/api/fotos/${encodeURIComponent(foto.id)}/vista`;
    const linea = crear("div", "linea");
    const deslizador = crear("input", "deslizador");
    deslizador.type = "range";
    deslizador.min = "0";
    deslizador.max = "100";
    deslizador.value = "50";
    deslizador.setAttribute("aria-label", `Comparar el antes y el después de ${foto.archivo}`);
    deslizador.addEventListener("input", () => comparador.style.setProperty("--corte", `${deslizador.value}%`));
    const espera = crear("div", "espera");
    comparador.append(
      despues, antes, linea, crear("span", "rotulo rotulo-antes", "Antes"),
      crear("span", "rotulo rotulo-despues", "Después"), deslizador, espera,
    );

    const pie = crear("div", "foto-pie");
    const textos = crear("div");
    const nombre = crear("p", "foto-nombre", foto.archivo);
    const situacion = crear("p", "foto-estado");
    textos.append(nombre, situacion);
    const quitar = crear("button", "boton boton-enlace", "Quitar");
    quitar.type = "button";
    quitar.setAttribute("aria-label", `Quitar ${foto.archivo}`);
    quitar.addEventListener("click", async () => {
      try {
        await pedir("DELETE", `/api/fotos/${encodeURIComponent(foto.id)}`);
      } catch (error) {
        situacion.textContent = error.message;
      }
      refrescar();
    });
    pie.append(textos, quitar);

    const usar = crear("label", "foto-usar");
    const casilla = crear("input");
    casilla.type = "checkbox";
    casilla.checked = true;
    casilla.disabled = true;
    casilla.addEventListener("change", () => {
      if (casilla.checked) sinMarcar.delete(foto.id);
      else sinMarcar.add(foto.id);
      for (const alCambiar of alCambiarSeleccion) alCambiar();
    });
    usar.append(casilla, crear("span", null, "Usar esta foto"));

    const aviso = crear("p", "nota nota-aviso");
    const fallo = crear("p", "nota nota-error");
    elemento.append(comparador, pie, usar, aviso, fallo);
    return { elemento, comparador, despues, espera, situacion, usar, casilla, aviso, fallo, estado: null };
  }

  function actualizarTarjeta(tarjeta, foto) {
    if (tarjeta.estado !== foto.estado) {
      tarjeta.estado = foto.estado;
      const lista = foto.estado === "lista";
      tarjeta.comparador.classList.toggle("sin-recorte", !lista);
      if (lista) tarjeta.despues.src = `/api/fotos/${encodeURIComponent(foto.id)}/recorte`;
      mostrar(tarjeta.despues, lista);
      tarjeta.espera.textContent = ESTADOS[foto.estado] || "";
      mostrar(tarjeta.espera, Boolean(ESTADOS[foto.estado]));
      tarjeta.casilla.disabled = !lista;
      mostrar(tarjeta.usar, lista);
    }
    let situacion = `${foto.ancho}×${foto.alto} px`;
    if (foto.estado === "lista" && foto.segundos !== null) {
      situacion += ` · ${String(foto.segundos).replace(".", ",")}\u00a0s`; // lo que tardó el recorte
    }
    tarjeta.situacion.textContent = situacion;
    tarjeta.aviso.textContent = foto.aviso || "";
    mostrar(tarjeta.aviso, Boolean(foto.aviso));
    tarjeta.fallo.textContent = foto.error || "";
    mostrar(tarjeta.fallo, Boolean(foto.error));
  }

  pintores.push((actual) => {
    const lista = $("lista-fotos");
    const vivos = new Set(actual.fotos.map((foto) => foto.id));
    for (const [id, tarjeta] of tarjetas) {
      if (!vivos.has(id)) {
        tarjeta.elemento.remove();
        tarjetas.delete(id);
        sinMarcar.delete(id);
      }
    }
    for (const foto of actual.fotos) {
      let tarjeta = tarjetas.get(foto.id);
      if (!tarjeta) {
        tarjeta = crearTarjeta(foto);
        tarjetas.set(foto.id, tarjeta);
        lista.append(tarjeta.elemento);
      }
      actualizarTarjeta(tarjeta, foto);
    }
    mostrar($("tarjeta-fotos"), actual.fotos.length > 0);
  });

  $("empezar-de-nuevo").addEventListener("click", async () => {
    try {
      await pedir("DELETE", "/api/fotos");
      pintarNotas($("avisos-subida"), []);
    } catch (error) {
      pintarNotas($("avisos-subida"), [{ clase: "nota-error", texto: error.message }]);
    }
    refrescar();
  });

  // --- Zona Fotos: fondo blanco y medidas -------------------------------------------------------------------------

  const casillasPlataforma = new Map(); // id de la plataforma → su casilla

  function plataformasElegidas() {
    return [...casillasPlataforma].filter(([, casilla]) => casilla.checked).map(([id]) => id);
  }

  function pintarPlataformas() {
    const lista = $("lista-plataformas");
    casillasPlataforma.clear();
    lista.replaceChildren();
    $("error-plataformas").textContent = opciones.error_plataformas || "";
    mostrar($("error-plataformas"), Boolean(opciones.error_plataformas));
    for (const plataforma of opciones.plataformas) {
      const elemento = crear("li");
      const etiqueta = crear("label", "plataforma");
      const casilla = crear("input");
      casilla.type = "checkbox";
      casilla.checked = true;
      casilla.value = plataforma.id;
      casilla.addEventListener("change", pintarResumenMedidas);
      casillasPlataforma.set(plataforma.id, casilla);
      const textos = crear("span");
      textos.append(
        crear("span", "plataforma-nombre", plataforma.nombre),
        crear(
          "span", "plataforma-medida",
          `${plataforma.medida} · producto al ${plataforma.porcentaje} % · ${plataforma.peso_maximo}`,
        ),
        crear("span", "plataforma-dice", plataforma.dice),
      );
      etiqueta.append(casilla, textos);
      elemento.append(etiqueta);
      lista.append(elemento);
    }
    pintarResumenMedidas();
  }

  function pintarResumenMedidas() {
    if (!estado || !opciones) return;
    const fotos = fotosElegidas().length;
    const plataformas = plataformasElegidas().length;
    const trabajando = estado.trabajos.medidas.estado === "trabajando";
    $("generar-medidas").disabled = trabajando || !fotos || !plataformas;
    let resumen = "";
    if (!fotos) resumen = "Marca al menos una foto ya recortada.";
    else if (!plataformas) resumen = "Elige al menos una plataforma.";
    else {
      const total = fotos * plataformas;
      resumen = `${fotos} ${fotos === 1 ? "foto" : "fotos"} × ${plataformas} ${plataformas === 1 ? "plataforma" : "plataformas"} = ${total} ${total === 1 ? "archivo" : "archivos"}`;
    }
    $("resumen-medidas").textContent = resumen;
  }
  alCambiarSeleccion.push(pintarResumenMedidas);

  for (const [boton, marcar] of [["plataformas-todas", true], ["plataformas-ninguna", false]]) {
    $(boton).addEventListener("click", () => {
      for (const casilla of casillasPlataforma.values()) casilla.checked = marcar;
      pintarResumenMedidas();
    });
  }

  let medidasPedidas = false; // para decir «listo» solo de un lote pedido desde esta página

  $("generar-medidas").addEventListener("click", async () => {
    mostrar($("error-medidas"), false);
    mostrar($("medidas-listas"), false);
    $("generar-medidas").disabled = true;
    try {
      await pedir("POST", "/api/medidas", { fotos: fotosElegidas(), plataformas: plataformasElegidas() });
      medidasPedidas = true;
    } catch (error) {
      $("error-medidas").textContent = error.message;
      mostrar($("error-medidas"), true);
    }
    refrescar();
  });

  $("ver-resultados").addEventListener("click", () => {
    irA("resultados");
    window.scrollTo(0, 0);
  });

  pintores.push((actual) => {
    const trabajo = actual.trabajos.medidas;
    mostrar($("tarjeta-medidas"), actual.fotos.some((foto) => foto.estado === "lista"));
    pintarAvance(trabajo, { caja: "avance-medidas", barra: "barra-medidas", texto: "texto-medidas", errores: "errores-medidas" });
    const listo = medidasPedidas && trabajo.estado === "terminado";
    if (listo) {
      const hechos = trabajo.total - trabajo.errores.length;
      $("texto-medidas-listas").textContent =
        `Listo: ${hechos} ${hechos === 1 ? "archivo creado" : "archivos creados"}. Míralos y descárgalos en Resultados.`;
    }
    mostrar($("medidas-listas"), listo);
    pintarResumenMedidas();
  });

  // --- Zona Fotos: escenas con IA ---------------------------------------------------------------------------------
  // Gastar dinero va en dos pasos: «Ver el costo» (no gasta) y, con el costo a la vista, «Sí, generar».

  let estimacion = null; // la última estimación que se le enseñó al usuario, con el pedido tal como se estimó
  let escenasPedidas = false; // para decir «listo» solo de un lote pedido desde esta página

  function pedidoDeEscenas() {
    const escena = $("escena").value;
    return {
      fotos: fotosElegidas(),
      escena,
      formato: $("formato-escena").value,
      propia: escena === opciones.escena_propia.id ? $("escena-propia").value : null,
      color: escena === opciones.escena_color.id ? $("color-escena").value : null, // solo el fondo liso lleva color
    };
  }

  /** Si cambia lo que se va a pedir, la estimación ya no vale: hay que volver a ver el costo. */
  function olvidarEstimacion() {
    estimacion = null;
    mostrar($("confirmar-escenas"), false);
    decir("error-escenas", "");
    pintarResumenEscenas();
  }

  function pintarOpcionesDeEscenas() {
    const escenas = opciones.escenas.map((escena) => {
      const opcion = crear("option", null, escena.nombre);
      opcion.value = escena.id;
      return opcion;
    });
    const propia = crear("option", null, "Escribir la mía…");
    propia.value = opciones.escena_propia.id;
    $("escena").replaceChildren(...escenas, propia);
    $("formato-escena").replaceChildren(...opciones.formatos.map((formato) => {
      const opcion = crear("option", null, formato);
      opcion.value = formato;
      return opcion;
    }));
    $("escena-propia").maxLength = opciones.escena_propia.maximo;
    $("color-escena").value = opciones.escena_color.por_defecto.toLowerCase(); // gris claro, si no se elige otro
    $("marca-escenas").textContent = opciones.marca_escenas;
    $("nota-escenas").textContent = opciones.nota_escenas;
    pintarResumenEscenas();
  }

  function pintarResumenEscenas() {
    if (!estado || !opciones) return;
    const fotos = fotosElegidas().length;
    const trabajando = estado.trabajos.escenas.estado === "trabajando";
    const modelo = opciones.modelos_escenas.find((m) => m.id === estado.ajustes.modelo_escenas);
    mostrar($("campo-escena-propia"), $("escena").value === opciones.escena_propia.id);
    mostrar($("campo-color-escena"), $("escena").value === opciones.escena_color.id);
    $("texto-color-escena").textContent = $("color-escena").value.toUpperCase();
    $("ver-costo").disabled = trabajando || !fotos;
    $("generar-escenas").disabled = trabajando;
    let resumen = "Marca al menos una foto ya recortada.";
    if (fotos) {
      resumen = `${fotos} ${fotos === 1 ? "foto marcada = 1 escena" : `fotos marcadas = ${fotos} escenas`}`;
      if (modelo) resumen += ` · modelo ${modelo.nombre}`;
    }
    $("resumen-escenas").textContent = resumen;
  }
  alCambiarSeleccion.push(olvidarEstimacion);

  for (const campo of ["escena", "formato-escena", "escena-propia", "color-escena"]) {
    $(campo).addEventListener("input", olvidarEstimacion);
  }

  $("ver-costo").addEventListener("click", async () => {
    olvidarEstimacion();
    mostrar($("escenas-listas"), false);
    escenasPedidas = false;
    const pedido = pedidoDeEscenas();
    try {
      const respuesta = await pedir("POST", "/api/escenas/estimar", pedido);
      if (!respuesta.se_puede) {
        // No se gasta: falta la clave, o el costo supera lo que queda del tope de la sesión.
        decir("error-escenas", `${respuesta.texto.replace(" · ¿Generar?", "")}. ${respuesta.mensaje}`);
        return;
      }
      estimacion = { pedido, costo: respuesta.costo_estimado_usd };
      $("texto-estimacion").textContent = respuesta.texto;
      mostrar($("confirmar-escenas"), true);
      $("generar-escenas").focus();
    } catch (error) {
      decir("error-escenas", error.message);
    }
  });

  $("cancelar-escenas").addEventListener("click", olvidarEstimacion);

  $("generar-escenas").addEventListener("click", async () => {
    if (!estimacion) return;
    const { pedido, costo } = estimacion;
    $("generar-escenas").disabled = true;
    try {
      // Se envía el mismo pedido que se estimó y el costo que vio el usuario: si ya no coincide, el servidor no gasta.
      await pedir("POST", "/api/escenas", { ...pedido, confirmado: true, costo_estimado_usd: costo });
      olvidarEstimacion();
      escenasPedidas = true;
    } catch (error) {
      olvidarEstimacion();
      decir("error-escenas", error.message);
    }
    refrescar();
  });

  $("ir-a-ajustes").addEventListener("click", () => {
    irA("ajustes");
    window.scrollTo(0, 0);
  });

  $("ver-escenas").addEventListener("click", () => {
    irA("resultados");
    window.scrollTo(0, 0);
  });

  pintores.push((actual) => {
    if (!opciones) return;
    const trabajo = actual.trabajos.escenas;
    mostrar($("tarjeta-escenas"), actual.fotos.some((foto) => foto.estado === "lista"));
    $("texto-escenas-sin-clave").textContent = "Para las escenas con IA hace falta una clave de OpenRouter.";
    mostrar($("escenas-sin-clave"), !actual.clave.guardada);
    pintarAvance(trabajo, { caja: "avance-escenas", barra: "barra-escenas", texto: "texto-escenas", errores: "errores-escenas" });

    const terminado = trabajo.estado === "terminado";
    // Si el lote se detuvo (sin saldo, sin conexión, tope de la sesión…), se dice por qué.
    $("escenas-detenidas").textContent = terminado && trabajo.detenido ? `El lote se detuvo. ${trabajo.mensaje || ""}`.trim() : "";
    mostrar($("escenas-detenidas"), terminado && Boolean(trabajo.detenido));

    const listo = escenasPedidas && terminado;
    if (listo) {
      const hechas = trabajo.hechas;
      let texto = hechas === 0 ? "No se generó ninguna escena" : `Listo: ${hechas} ${hechas === 1 ? "escena" : "escenas"}`;
      texto += ` · costo real ${trabajo.costo_real} (estimado ${trabajo.costo_estimado}).`;
      if (trabajo.costo_sin_informar) texto += " OpenRouter no informó el costo de alguna escena: se cuenta el estimado.";
      texto += ` En esta sesión llevas ${actual.gasto.sesion} de ${actual.gasto.tope}.`;
      $("texto-escenas-listas").textContent = texto;
      $("escenas-listas").className = hechas > 0 ? "nota nota-bien fila-entre" : "nota fila-entre";
      mostrar($("ver-escenas"), hechas > 0);
    }
    mostrar($("escenas-listas"), listo);
    pintarResumenEscenas();
  });

  // --- Zona Resultados: una cuadrícula por foto y las descargas ---------------------------------------------------

  let resultadosPintados = "";

  function crearResultado({ titulo, archivo, datos, url, avisos, cuadros, marca }) {
    const elemento = crear("li", "resultado");
    const marco = crear("a", cuadros ? "resultado-imagen cuadros" : "resultado-imagen");
    marco.href = url;
    marco.target = "_blank";
    marco.rel = "noopener";
    const imagen = crear("img");
    imagen.loading = "lazy";
    imagen.decoding = "async";
    imagen.alt = `${titulo}: ${archivo}`;
    imagen.src = url;
    marco.append(imagen);
    elemento.append(marco, crear("p", "resultado-titulo", titulo));
    if (marca) elemento.append(crear("p", "chip", marca));
    elemento.append(crear("p", "resultado-archivo", archivo), crear("p", "resultado-datos", datos));
    for (const aviso of avisos) elemento.append(crear("p", "nota nota-aviso", aviso));
    const descargar = crear("a", "boton boton-enlace", "Descargar");
    descargar.href = url;
    descargar.download = archivo;
    elemento.append(descargar);
    return elemento;
  }

  function botonDescarga(texto, plataforma) {
    const boton = crear("a", plataforma ? "boton" : "boton boton-principal", texto);
    boton.href = plataforma ? `/api/descargar?plataforma=${encodeURIComponent(plataforma)}` : "/api/descargar";
    boton.download = "";
    if (plataforma) boton.dataset.plataforma = plataforma;
    return boton;
  }

  pintores.push((actual) => {
    const conResultados = actual.fotos.filter((foto) => foto.recorte);
    // Solo se vuelve a pintar si cambió algún archivo (así las imágenes no parpadean en cada consulta).
    const huella = JSON.stringify(conResultados.map((foto) => [
      foto.id, foto.recorte.archivo, foto.salidas.map((s) => [s.archivo, s.peso]), (foto.escenas || []).map((e) => e.archivo),
    ]));
    if (huella === resultadosPintados) return;
    resultadosPintados = huella;

    mostrar($("sin-resultados"), conResultados.length === 0);
    mostrar($("descargas"), conResultados.length > 0);

    const bloques = conResultados.map((foto) => {
      const bloque = crear("div", "tarjeta resultado-foto");
      bloque.dataset.id = foto.id;
      bloque.append(crear("h3", null, foto.archivo));
      const lista = crear("ul", "resultado-fotos");
      lista.append(crearResultado({
        titulo: "Recorte",
        archivo: foto.recorte.archivo,
        datos: `PNG con transparencia · ${foto.recorte.medida} · ${foto.recorte.peso_texto}`,
        url: foto.recorte.url,
        avisos: [],
        cuadros: true,
      }));
      for (const salida of foto.salidas) {
        lista.append(crearResultado({
          titulo: salida.nombre_plataforma,
          archivo: salida.archivo,
          datos: `${salida.medida} · ${salida.peso_texto} · producto al ${salida.porcentaje} %`,
          url: salida.url,
          avisos: salida.avisos,
        }));
      }
      for (const escena of foto.escenas || []) {
        lista.append(crearResultado({
          titulo: `Escena: ${escena.escena}`,
          archivo: escena.archivo,
          datos: `${escena.formato} · ${escena.medida} · ${escena.peso_texto} · costo ${escena.costo}`,
          url: escena.url,
          avisos: escena.aviso ? [escena.aviso] : [],
          marca: escena.marca, // «Para redes y fotos secundarias»
        }));
      }
      bloque.append(lista);
      return bloque;
    });
    $("lista-resultados").replaceChildren(...bloques);

    const botones = [botonDescarga("Descargar todo (ZIP)", null)];
    const nombres = new Map();
    for (const foto of conResultados) for (const salida of foto.salidas) nombres.set(salida.plataforma, salida.nombre_plataforma);
    for (const [id, nombre] of nombres) botones.push(botonDescarga(`Solo ${nombre}`, id));
    const hayEscenas = conResultados.some((foto) => (foto.escenas || []).length > 0);
    if (nombres.size > 0 || hayEscenas) botones.push(botonDescarga("Solo los recortes", "recortes"));
    if (hayEscenas) botones.push(botonDescarga("Solo las escenas", "escenas"));
    $("botones-descarga").replaceChildren(...botones);
  });

  // --- Zona Ajustes -----------------------------------------------------------------------------------------------

  /** Escribe el resultado de una acción (bien o error) en una nota. */
  function decir(id, texto, clase) {
    const nota = $(id);
    nota.textContent = texto || "";
    if (clase !== undefined) nota.className = `nota ${clase}`.trim();
    mostrar(nota, Boolean(texto));
  }

  // La clave: se envía una vez para guardarla y no vuelve nunca; la página solo recibe «••••» y los 4 últimos.
  $("guardar-clave").addEventListener("click", async () => {
    const campo = $("clave");
    try {
      await pedir("PUT", "/api/ajustes/clave", { clave: campo.value });
      campo.value = "";
      decir("resultado-clave", "Clave guardada. Pulsa «Probar» para comprobar la conexión.", "nota-bien");
    } catch (error) {
      decir("resultado-clave", error.message, "nota-error");
    }
    refrescar();
  });

  $("probar-clave").addEventListener("click", async () => {
    decir("resultado-clave", "Probando la conexión con OpenRouter…", "");
    $("probar-clave").disabled = true;
    try {
      const respuesta = await pedir("POST", "/api/ajustes/clave/probar");
      decir("resultado-clave", respuesta.mensaje, "nota-bien");
    } catch (error) {
      decir("resultado-clave", error.message, "nota-error");
    }
    $("probar-clave").disabled = false;
  });

  $("borrar-clave").addEventListener("click", async () => {
    try {
      await pedir("DELETE", "/api/ajustes/clave");
      decir("resultado-clave", "Clave borrada de este computador.", "");
    } catch (error) {
      decir("resultado-clave", error.message, "nota-error");
    }
    refrescar();
  });

  pintores.push((actual) => {
    mostrar($("clave-guardada"), actual.clave.guardada);
    $("mascara-clave").textContent = actual.clave.mascara || "";
    $("etiqueta-clave").textContent = actual.clave.guardada ? "Cambiar la clave" : "Pega aquí tu clave";
    $("gasto-sesion").textContent =
      `Gastado en esta sesión: ${actual.gasto.sesion} de ${actual.gasto.tope} (quedan ${actual.gasto.queda}).`;
  });

  // El resto de ajustes: se rellenan una vez (y después de guardar), para no pisar lo que el usuario está escribiendo.
  let ajustesRellenos = false;

  function rellenarAjustes(actual) {
    for (const radio of document.querySelectorAll('input[name="calidad"]')) {
      radio.checked = radio.value === actual.ajustes.calidad_recorte;
    }
    $("modelo-escenas").value = actual.ajustes.modelo_escenas;
    $("tope-sesion").value = String(actual.ajustes.tope_sesion_usd);
    ajustesRellenos = true;
  }

  function pintarModelosDeEscenas() {
    const lista = $("modelo-escenas");
    lista.replaceChildren(...opciones.modelos_escenas.map((modelo) => {
      const opcion = crear("option", null, `${modelo.nombre} · ${modelo.costo_partida} por imagen`);
      opcion.value = modelo.id;
      return opcion;
    }));
    if (estado) lista.value = estado.ajustes.modelo_escenas;
  }

  pintores.push((actual) => {
    if (!ajustesRellenos && opciones) rellenarAjustes(actual);
  });

  $("guardar-ajustes").addEventListener("click", async () => {
    mostrar($("ajustes-guardados"), false);
    const calidad = document.querySelector('input[name="calidad"]:checked');
    const tope = Number($("tope-sesion").value.replace(",", "."));
    try {
      if ($("tope-sesion").value.trim() === "" || Number.isNaN(tope)) {
        throw new Error("El tope de gasto debe ser un número, por ejemplo 1.");
      }
      await pedir("PUT", "/api/ajustes", {
        calidad_recorte: calidad ? calidad.value : "automatica",
        modelo_escenas: $("modelo-escenas").value,
        tope_sesion_usd: tope,
      });
      decir("error-ajustes", "");
      mostrar($("ajustes-guardados"), true);
      ajustesRellenos = false; // se vuelven a leer tal como quedaron guardados
    } catch (error) {
      decir("error-ajustes", error.message);
    }
    refrescar();
  });

  // --- Arranque ---------------------------------------------------------------------------------------------------

  async function cargarOpciones() {
    try {
      opciones = await pedir("GET", "/api/opciones");
      pintarPlataformas();
      pintarOpcionesDeEscenas();
      pintarModelosDeEscenas();
      if (estado) for (const pintar of pintores) pintar(estado);
    } catch (error) {
      setTimeout(cargarOpciones, 2000);
    }
  }

  irA(location.hash.slice(1));
  refrescar().then(cargarOpciones);
})();
