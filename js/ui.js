// Utilidades de interfaz compartidas por todos los módulos.
export const $ = (selector, raiz = document) => raiz.querySelector(selector);
export const $$ = (selector, raiz = document) => [...raiz.querySelectorAll(selector)];

const formatoPesos = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const formatoFecha = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" });
const formatoDia = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium" });

export const pesos = (valor) => formatoPesos.format(Number(valor || 0));
export const numero = (valor) => Number(valor || 0);

export function fecha(valor) {
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? "—" : formatoFecha.format(d);
}

export function dia(valor) {
  // "2026-11-16" se interpreta como fecha local (no UTC) para no correr el día.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(String(valor)) ? new Date(`${valor}T00:00:00`) : new Date(valor);
  return Number.isNaN(d.getTime()) ? "—" : formatoDia.format(d);
}

// Fecha local en formato AAAA-MM-DD (para inputs type="date" y filtros de la API).
export function hoyISO(desplazamientoDias = 0) {
  const d = new Date();
  d.setDate(d.getDate() + desplazamientoDias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const esc = (texto) =>
  String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export const opciones = (lista, { vacio = "Selecciona…", valor = "id", texto = "nombre" } = {}) =>
  (vacio === null ? "" : `<option value="">${esc(vacio)}</option>`) +
  lista.map((x) => `<option value="${esc(x[valor])}">${esc(typeof texto === "function" ? texto(x) : x[texto])}</option>`).join("");

// ---------------------------------------------------------------------------
// Mensajes de estado (barra superior)
// ---------------------------------------------------------------------------
let temporizador = null;
export function avisar(mensaje, { error = false, cargando = false } = {}) {
  const caja = $("#status");
  clearTimeout(temporizador);
  caja.hidden = false;
  $("#status-message").textContent = mensaje;
  $("#loading-spinner").hidden = !cargando;
  caja.setAttribute("aria-busy", String(cargando));
  caja.classList.toggle("is-error", error);
  if (!error && !cargando) temporizador = setTimeout(() => { caja.hidden = true; }, 6000);
}

export function ocultarAviso() {
  $("#status").hidden = true;
}

// Ejecuta una petición mostrando "cargando", desactiva el botón para evitar doble clic
// y muestra el error del backend si falla. Devuelve el resultado o lanza el error.
export async function ejecutar(trabajo, { exito = "", cargando = "Procesando…", boton = null } = {}) {
  if (boton) boton.disabled = true;
  avisar(cargando, { cargando: true });
  try {
    const resultado = await trabajo();
    if (exito) avisar(exito);
    else ocultarAviso();
    return resultado;
  } catch (error) {
    avisar(error.message || "Ocurrió un error inesperado.", { error: true });
    throw error;
  } finally {
    if (boton) boton.disabled = false;
  }
}

// Igual que ejecutar(), pero sin relanzar el error (para manejadores de clic).
export async function intentar(trabajo, opcionesEjecucion) {
  try {
    return await ejecutar(trabajo, opcionesEjecucion);
  } catch {
    return undefined;
  }
}

export const confirmar = (mensaje) => window.confirm(mensaje);

// ---------------------------------------------------------------------------
// Formulario en diálogo reutilizable
// campos: [{ nombre, etiqueta, tipo, requerido, opciones (HTML), min, max, paso, ayuda, ancho: "completo" }]
// construir(contenedor): agrega contenido propio (líneas de productos, notas...).
// recolectar(datos, contenedor): completa los datos antes de guardar.
// alGuardar(datos): hace la petición; si lanza un error se muestra en el diálogo.
// ---------------------------------------------------------------------------
let formularioActual = null;

export function abrirFormulario({
  titulo, kicker = "Registro", nota = "", campos = [], valores = {}, construir, recolectar,
  alGuardar, textoGuardar = "Guardar",
}) {
  formularioActual = { campos, recolectar, alGuardar };
  $("#dialog-title").textContent = titulo;
  $("#dialog-kicker").textContent = kicker;
  $("#record-id-note").textContent = nota;
  $("#dialog-error").textContent = "";
  $("#dialog-save").textContent = textoGuardar;
  const contenedor = $("#dialog-fields");
  contenedor.replaceChildren();

  for (const campo of campos) {
    const etiqueta = document.createElement("label");
    etiqueta.dataset.campo = campo.nombre;
    if (campo.ancho === "completo") etiqueta.classList.add("span-2");
    let control;
    if (campo.tipo === "select") {
      control = document.createElement("select");
      control.innerHTML = campo.opciones || "";
    } else if (campo.tipo === "textarea") {
      control = document.createElement("textarea");
    } else {
      control = document.createElement("input");
      control.type = campo.tipo || "text";
      if (campo.min !== undefined) control.min = campo.min;
      if (campo.max !== undefined) control.max = campo.max;
      if (campo.tipo === "number") control.step = campo.paso ?? "1";
    }
    control.name = campo.nombre;
    if (campo.requerido) control.required = true;
    const valor = valores[campo.nombre];
    if (campo.tipo === "checkbox") {
      etiqueta.classList.add("checkbox-label");
      control.checked = Boolean(valor);
      etiqueta.append(control, document.createTextNode(campo.etiqueta));
    } else {
      control.value = valor ?? "";
      etiqueta.append(document.createTextNode(campo.etiqueta + (campo.requerido ? " *" : "")), control);
    }
    if (campo.ayuda) {
      const ayuda = document.createElement("small");
      ayuda.className = "field-help";
      ayuda.textContent = campo.ayuda;
      etiqueta.append(ayuda);
    }
    contenedor.append(etiqueta);
  }
  construir?.(contenedor);
  $("#record-dialog").showModal();
  contenedor.querySelector("input:not([type=checkbox]),select,textarea")?.focus();
}

export function cerrarFormulario() {
  formularioActual = null;
  if ($("#record-dialog").open) $("#record-dialog").close();
}

function leerCampos() {
  const datos = {};
  const contenedor = $("#dialog-fields");
  for (const campo of formularioActual.campos) {
    const control = contenedor.querySelector(`[name="${campo.nombre}"]`);
    if (!control) continue;
    if (campo.tipo === "checkbox") datos[campo.nombre] = control.checked;
    else if (campo.tipo === "number") datos[campo.nombre] = control.value === "" ? null : Number(control.value);
    else datos[campo.nombre] = control.value.trim();
  }
  return datos;
}

export function iniciarFormularios() {
  $("#record-form").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!formularioActual) return;
    const formulario = $("#record-form");
    if (!formulario.reportValidity()) return;
    const boton = $("#dialog-save");
    $("#dialog-error").textContent = "";
    try {
      let datos = leerCampos();
      if (formularioActual.recolectar) datos = formularioActual.recolectar(datos, $("#dialog-fields"));
      boton.disabled = true;
      await formularioActual.alGuardar(datos);
      cerrarFormulario();
    } catch (error) {
      $("#dialog-error").textContent = error.message || "No se pudo guardar.";
    } finally {
      boton.disabled = false;
    }
  });
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("[data-close]")) cerrarFormulario();
  });
  $("#record-dialog").addEventListener("close", () => {
    formularioActual = null;
  });
}
