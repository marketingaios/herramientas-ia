/* Estudio de fotos de producto: la página.
   Sin librerías y sin nada de internet. Todo lo que viene del usuario o del servidor (nombres de archivo, el nombre
   del negocio, los mensajes) se escribe siempre como texto (textContent), nunca como HTML. */
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
  let temporizador = null;
  const pintores = [];

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

  // --- La marca del negocio y los avisos generales ----------------------------------------------------------------

  pintores.push((actual) => {
    const negocio = actual.negocio;
    const raiz = document.documentElement.style;
    raiz.setProperty("--color-principal", negocio.color_principal);
    raiz.setProperty("--color-acento", negocio.color_acento);
    raiz.setProperty("--color-sobre-principal", negocio.sobre_principal);
    raiz.setProperty("--color-sobre-acento", negocio.sobre_acento);

    $("nombre-negocio").textContent = negocio.nombre;
    mostrar($("nombre-negocio"), Boolean(negocio.nombre));
    document.title = negocio.nombre ? `Estudio de fotos · ${negocio.nombre}` : "Estudio de fotos de producto";

    const logo = $("logo-negocio");
    if (negocio.logo && logo.getAttribute("src") !== negocio.logo) logo.src = negocio.logo;
    mostrar(logo, Boolean(negocio.logo));

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

    const aviso = crear("p", "nota nota-aviso");
    const fallo = crear("p", "nota nota-error");
    elemento.append(comparador, pie, aviso, fallo);
    return { elemento, comparador, despues, espera, situacion, aviso, fallo, estado: null };
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

  // --- Arranque ---------------------------------------------------------------------------------------------------

  irA(location.hash.slice(1));
  refrescar();
})();
