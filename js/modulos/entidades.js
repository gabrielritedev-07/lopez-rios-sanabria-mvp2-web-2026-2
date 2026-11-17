// Categorías, proveedores y clientes.
// Permisos: clientes -> administrador y cajero. Categorías y proveedores -> el cajero solo consulta.
import { api } from "../api.js";
import { cargar, estado, porId, reemplazar } from "../estado.js";
import { esAdmin } from "../sesion.js";
import { $, $$, abrirFormulario, avisar, confirmar, ejecutar, esc, intentar } from "../ui.js";

const TEXTOS = {
  categorias: { singular: "categoría", plural: "Categorías", nuevo: "Nueva categoría", boton: "+ Categoría", guardado: "guardada" },
  proveedores: { singular: "proveedor", plural: "Proveedores", nuevo: "Nuevo proveedor", boton: "+ Proveedor", guardado: "guardado" },
  clientes: { singular: "cliente", plural: "Clientes", nuevo: "Nuevo cliente", boton: "+ Cliente", guardado: "guardado" },
};
let entidad = "categorias";
const alCambiarClientes = new Set();

const puedeGestionar = (nombre = entidad) => nombre === "clientes" || esAdmin();

export function suscribirClientes(callback) {
  alCambiarClientes.add(callback);
}
const avisarClientes = () => alCambiarClientes.forEach((cb) => cb());

function render() {
  const texto = $("#entity-search").value.trim().toLowerCase();
  const gestionar = puedeGestionar();
  $("#new-entity").hidden = !gestionar;
  $("#new-entity").textContent = TEXTOS[entidad].boton;
  const registros = estado[entidad].filter((x) =>
    `${x.nombre} ${x.telefono || ""} ${x.correo || ""}`.toLowerCase().includes(texto),
  );
  $("#entity-list").innerHTML =
    registros
      .map(
        (x) => `<article class="sale-record">
          <div><h2>${esc(x.nombre)}</h2><p>${esc([x.telefono, x.correo].filter(Boolean).join(" · ") || (entidad === "categorias" ? `ID ${x.id}` : "Sin datos de contacto"))}</p></div>
          <div class="sale-record__actions">${
            gestionar
              ? `<button class="button button--secondary" type="button" data-entity-edit="${x.id}">Editar</button><button class="button button--danger" type="button" data-entity-delete="${x.id}">Eliminar</button>`
              : '<span class="tag tag--muted">Solo consulta</span>'
          }</div>
        </article>`,
      )
      .join("") || '<p class="empty-list">No hay registros.</p>';
}

function camposDe(nombre) {
  if (nombre === "categorias") return [{ nombre: "nombre", etiqueta: "Nombre", requerido: true, ancho: "completo" }];
  return [
    { nombre: "nombre", etiqueta: "Nombre", requerido: true, ancho: "completo" },
    { nombre: "telefono", etiqueta: "Teléfono", tipo: "tel" },
    { nombre: "correo", etiqueta: "Correo", tipo: "email" },
  ];
}

function abrirFormularioEntidad(nombre, registro = null, alGuardarExtra = null) {
  abrirFormulario({
    titulo: registro ? `Editar ${TEXTOS[nombre].singular}` : TEXTOS[nombre].nuevo,
    kicker: TEXTOS[nombre].plural,
    nota: registro ? `ID ${registro.id}` : "",
    campos: camposDe(nombre),
    valores: registro ?? {},
    alGuardar: async (datos) => {
      const guardado = registro
        ? await api.patch(`${nombre}/${registro.id}/`, datos)
        : await api.post(`${nombre}/`, datos);
      reemplazar(nombre, guardado);
      if (nombre === entidad) render();
      if (nombre === "clientes") avisarClientes();
      avisar(`“${guardado.nombre}” ${TEXTOS[nombre].guardado}.`);
      alGuardarExtra?.(guardado);
    },
  });
}

// Usado desde el punto de venta: "+ Cliente" crea el cliente y lo deja seleccionado.
export function abrirFormularioCliente(alCrear) {
  abrirFormularioEntidad("clientes", null, alCrear);
}

async function eliminar(id, boton) {
  const registro = porId(entidad, id);
  if (!registro || !confirmar(`¿Eliminar “${registro.nombre}”?`)) return;
  const nombre = entidad;
  const resultado = await intentar(() => api.del(`${nombre}/${id}/`), {
    exito: `“${registro.nombre}” eliminado.`,
    boton,
  });
  if (resultado === null) {
    estado[nombre] = estado[nombre].filter((x) => x.id !== registro.id);
    render();
    if (nombre === "clientes") avisarClientes();
  }
}

async function cambiarEntidad(nombre) {
  entidad = nombre;
  $$("[data-entity]").forEach((b) => b.classList.toggle("is-selected", b.dataset.entity === nombre));
  $("#entity-search").value = "";
  await ejecutar(() => cargar(nombre), { cargando: `Cargando ${TEXTOS[nombre].plural.toLowerCase()}…` });
  render();
}

export async function mostrar() {
  await cambiarEntidad(entidad);
}

export function iniciar() {
  $(".entity-tabs").addEventListener("click", (e) => {
    const tab = e.target.closest("[data-entity]");
    if (tab) cambiarEntidad(tab.dataset.entity).catch(() => {});
  });
  $("#entity-search").addEventListener("input", render);
  $("#new-entity").addEventListener("click", () => abrirFormularioEntidad(entidad));
  $("#entity-list").addEventListener("click", (e) => {
    const editar = e.target.closest("[data-entity-edit]");
    if (editar) return abrirFormularioEntidad(entidad, porId(entidad, editar.dataset.entityEdit));
    const borrar = e.target.closest("[data-entity-delete]");
    if (borrar) eliminar(Number(borrar.dataset.entityDelete), borrar);
  });
}
