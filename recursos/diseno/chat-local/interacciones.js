"use strict";
// Prototipo efimero: no red, almacenamiento persistente ni ejecucion de modelos.
const elemento = (id) => document.getElementById(id);
const conversaciones = [
  { id: 1, titulo: "Criterios para clasificar negocios", detalle: "Hoy · Idioma y actividad", mensajes: [
    ["usuario", "Quiero evaluar el idioma de un comentario y clasificar la actividad del negocio. ¿Cómo conviene separar los criterios?"],
    ["asistente", "Podemos trabajar con dos evaluaciones independientes.\n\nIdioma del texto: español, otro idioma o indeterminado cuando falte evidencia.\n\nActividad del negocio: una categoría basada únicamente en la descripción disponible.\n\nAl preparar el trabajo, tú decides qué columnas alimentan cada evaluación y dónde se guarda cada resultado."],
    ["usuario", "Me interesa que la falta de información no termine convertida en una clasificación inventada."]
  ] },
  { id: 2, titulo: "Prompts para textos en español", detalle: "Hoy · Criterios reutilizables", mensajes: [
    ["usuario", "Ayúdame a redactar una evaluación del idioma de un texto."],
    ["asistente", "Define el criterio con evidencia observable y conserva una categoría de indeterminación. Esta conversación es un ejemplo del diseño."]
  ] },
  { id: 3, titulo: "Revisar categorías de actividad", detalle: "Ayer · Clasificación de negocios", mensajes: [
    ["usuario", "Quiero revisar las categorías de actividad antes de procesar un archivo."],
    ["asistente", "Podemos revisar categorías y casos ambiguos aquí. La selección de columnas permanecerá en la preparación del trabajo."]
  ] }
];
let actual = 1;
let estado = "normal";
let siguienteId = 4;
conversaciones[0].resumen = "Estamos definiendo criterios para clasificar negocios. Evaluaremos idioma del texto y actividad. La falta de evidencia debe producir un resultado indeterminado.";
const obtenerActual = () => conversaciones.find((conversacion) => conversacion.id === actual);

function pintarHistorial() {
  elemento("lista").replaceChildren();
  for (const conversacion of conversaciones) {
    const boton = document.createElement("button");
    boton.className = "conversacion";
    const titulo = document.createElement("strong");
    const detalle = document.createElement("small");
    titulo.textContent = conversacion.titulo;
    detalle.textContent = conversacion.detalle;
    boton.append(titulo, detalle);
    if (conversacion.id === actual) boton.setAttribute("aria-current", "page");
    boton.addEventListener("click", () => { actual = conversacion.id; estado = "normal"; elemento("vista").value = "normal"; pintar(); });
    elemento("lista").append(boton);
  }
}

function pintarMensajes() {
  const conversacion = obtenerActual();
  elemento("mensajes").replaceChildren();
  if (!conversacion.mensajes.length) {
    const vacio = document.createElement("div");
    vacio.className = "vacio";
    const titulo = document.createElement("h2");
    const texto = document.createElement("p");
    titulo.textContent = "Dale espacio a la siguiente idea.";
    texto.textContent = "Empieza con una pregunta. El contexto pertenecerá a esta conversación.";
    vacio.append(titulo, texto);
    elemento("mensajes").append(vacio);
  }
  for (const [rol, contenido] of conversacion.mensajes) {
    const mensaje = document.createElement("article");
    mensaje.className = `mensaje ${rol}`;
    const autor = document.createElement("div");
    autor.className = "autor";
    autor.textContent = rol === "usuario" ? "TÚ" : "ASISTENTE LOCAL";
    const texto = document.createElement("p");
    texto.textContent = contenido;
    mensaje.append(autor, texto);
    elemento("mensajes").append(mensaje);
  }
}

function pintar() {
  elemento("titulo").textContent = obtenerActual().titulo;
  elemento("entrada").value = obtenerActual().borrador || "";
  pintarHistorial();
  pintarMensajes();
  const avisos = {
    desconectado: "Ollama no está disponible. Tu borrador se conserva; podrás conectar antes de enviar.",
    lleno: "Se alcanzó el límite del historial. Borra una conversación elegida por ti para liberar espacio. Tu borrador se conserva.",
    generando: "El modelo está respondiendo. Puedes detener la respuesta sin perder los mensajes anteriores."
  };
  elemento("aviso").hidden = !avisos[estado];
  elemento("aviso").textContent = avisos[estado] || "";
  elemento("enviar").disabled = ["desconectado", "lleno"].includes(estado);
  elemento("borrar").disabled = estado === "generando";
  elemento("enviar").textContent = estado === "generando" ? "Detener" : "Enviar →";
  elemento("conexion").textContent = estado === "desconectado" ? "Sin conexión" : "Modelo local seleccionado";
}

function nuevaConversacion() {
  const conversacion = { id: siguienteId++, titulo: "Nueva conversación", detalle: "Ahora · Sin mensajes", mensajes: [] };
  conversaciones.unshift(conversacion);
  actual = conversacion.id;
  estado = "normal";
  elemento("entrada").value = "";
  pintar();
  elemento("entrada").focus();
}

elemento("nuevo").addEventListener("click", nuevaConversacion);
elemento("ver-memoria").addEventListener("click", () => {
  elemento("resumen").value = obtenerActual().resumen || "";
  elemento("memoria").showModal();
});
elemento("memoria").addEventListener("close", () => {
  if (elemento("memoria").returnValue === "guardar") obtenerActual().resumen = elemento("resumen").value;
});
elemento("entrada").addEventListener("input", () => { obtenerActual().borrador = elemento("entrada").value; });
elemento("renombrar").addEventListener("click", () => {
  elemento("nombre").value = obtenerActual().titulo;
  elemento("editor-nombre").showModal();
});
elemento("cancelar-nombre").addEventListener("click", () => elemento("editor-nombre").close());
elemento("form-nombre").addEventListener("submit", (evento) => {
  evento.preventDefault();
  const nombre = elemento("nombre").value.trim();
  if (!nombre) return;
  obtenerActual().titulo = nombre;
  elemento("editor-nombre").close();
  pintar();
});
elemento("borrar").addEventListener("click", () => elemento("confirmacion").showModal());
elemento("confirmacion").addEventListener("close", () => {
  if (elemento("confirmacion").returnValue !== "borrar") return;
  conversaciones.splice(conversaciones.findIndex((conversacion) => conversacion.id === actual), 1);
  if (!conversaciones.length) nuevaConversacion();
  else { actual = conversaciones[0].id; estado = "normal"; pintar(); }
});
elemento("formulario").addEventListener("submit", (evento) => {
  evento.preventDefault();
  if (estado === "generando") { estado = "normal"; pintar(); return; }
  if (["lleno", "desconectado"].includes(estado)) return;
  const texto = elemento("entrada").value.trim();
  if (!texto) return;
  const conversacion = obtenerActual();
  if (!conversacion.mensajes.length) conversacion.titulo = Array.from(texto.split("\n")[0]).slice(0, 60).join("");
  conversacion.mensajes.push(["usuario", texto]);
  conversacion.mensajes.push(["asistente", "Vista previa: aquí aparecerá la respuesta de Ollama. Este plano no ejecuta modelos ni guarda tus mensajes."]);
  conversacion.borrador = "";
  elemento("entrada").value = "";
  pintar();
});
elemento("entrada").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey && !evento.isComposing) {
    evento.preventDefault();
    elemento("formulario").requestSubmit();
  }
});
elemento("vista").addEventListener("change", () => {
  estado = elemento("vista").value;
  if (estado === "vacio") nuevaConversacion();
  else pintar();
});
pintar();
