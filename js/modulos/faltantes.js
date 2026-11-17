// Faltantes: registrar (ambos roles), listar y filtrar; resolver y vista para compras (administrador).
import { api } from "../api.js";
import { estado } from "../estado.js";
import { esAdmin } from "../sesion.js";
import { $, $$, abrirFormulario, avisar, confirmar, ejecutar, esc, fecha, intentar, opciones } from "../ui.js";

let pestana = "registros";
let registros = [];
let grupos = [];
const paginaVisible = () => $("#page-faltantes").classList.contains("is-active");

function filtros() {
  const datos = {
    tipo: $("#missing-filter-type").value,
    proveedor: $("#missing-filter-provider").value,
  };
  if (pestana === "registros") datos.estado = $("#missing-filter-state").value;
  return datos;
}

const etiquetaEstado = (f) =>
  f.estado === "pendiente" ? '<span class="tag tag--open">Pendiente</span>' : '<span class="tag tag--closed">Resuelto</span>';

function renderRegistros() {
  $("#missing-list").innerHTML =
    registros
      .map(
        (f) => `<article class="sale-record">
          <div><p class="eyebrow">${esc(f.tipoNombre)} · ${esc(fecha(f.fecha))}</p>
            <h2>${esc(f.nombre)} × ${f.cantidad} <span class="tags">${etiquetaEstado(f)}</span></h2>
            <p>Proveedor: ${esc(f.proveedorNombre || "sin asignar")} · registró ${esc(f.registradoPor)}${f.resueltoPor ? ` · resolvió ${esc(f.resueltoPor)}` : ""}</p></div>
          <div class="sale-record__actions">${
            esAdmin()
              ? `${f.estado === "pendiente" ? `<button class="button button--primary" type="button" data-missing-resolve="${f.id}">Marcar resuelto</button>` : ""}<button class="button button--danger" type="button" data-missing-delete="${f.id}">Eliminar</button>`
              : ""
          }</div>
        </article>`,
      )
      .join("") || '<p class="empty-list">No hay faltantes con estos filtros.</p>';
}

function renderGrupos() {
  $("#missing-list").innerHTML = grupos.length
    ? `<div class="table-wrap"><table><thead><tr><th>Producto</th><th>Proveedor</th><th class="num">Solicitudes</th><th class="num">Cantidad pedida</th><th class="num">Stock actual</th><th>Última solicitud</th><th></th></tr></thead><tbody>
      ${grupos
        .map(
          (g, i) => `<tr>
            <td><strong>${esc(g.nombre)}</strong><small>${g.productoId ? "En catálogo" : "No existe en catálogo"} · ${esc(g.tipos.join(", "))}</small></td>
            <td>${esc(g.proveedorNombre || "Sin proveedor")}</td>
            <td class="num">${g.solicitudes}</td>
            <td class="num">${g.cantidadTotal}</td>
            <td class="num">${g.stockActual ?? "—"}</td>
            <td>${esc(fecha(g.ultimaSolicitud))}</td>
            <td><div class="table-actions"><button type="button" data-group-resolve="${i}">Marcar resueltos</button></div></td>
          </tr>`,
        )
        .join("")}</tbody></table></div>`
    : '<p class="empty-list">No hay faltantes pendientes. 🎉</p>';
}

async function cargarLista() {
  if (pestana === "compras") {
    grupos = await ejecutar(() => api.get("faltantes/pendientes/", filtros()), { cargando: "Agrupando faltantes…" });
    renderGrupos();
  } else {
    registros = await ejecutar(() => api.get("faltantes/", filtros()), { cargando: "Cargando faltantes…" });
    renderRegistros();
  }
}

async function cambiarPestana(nombre) {
  pestana = nombre;
  $$("[data-missing-tab]").forEach((b) => b.classList.toggle("is-selected", b.dataset.missingTab === nombre));
  $("#missing-filter-state-wrap").hidden = nombre === "compras";
  await cargarLista();
}

// Formulario de registro. Si llega productoId (desde el punto de venta), se propone "agotado".
export function abrirRegistroFaltante({ productoId = null } = {}) {
  abrirFormulario({
    titulo: "Registrar faltante",
    kicker: "Demanda no atendida",
    nota: "Anota lo que pidió el cliente y no había, para tenerlo en cuenta en próximas compras.",
    textoGuardar: "Registrar",
    campos: [
      {
        nombre: "tipo", etiqueta: "Tipo", tipo: "select", requerido: true,
        opciones: '<option value="agotado">Agotado (existe en el catálogo)</option><option value="inexistente">Inexistente (no lo vendemos)</option>',
      },
      { nombre: "cantidad", etiqueta: "Cantidad solicitada", tipo: "number", min: 1, requerido: true },
      { nombre: "productoId", etiqueta: "Producto del catálogo", tipo: "select", opciones: opciones(estado.productos), ancho: "completo" },
      { nombre: "nombre", etiqueta: "Producto solicitado (descripción)", ancho: "completo", ayuda: "Ej.: Lápices de colores x 24" },
      { nombre: "proveedorId", etiqueta: "Proveedor sugerido (opcional)", tipo: "select", opciones: opciones(estado.proveedores, { vacio: "Sin proveedor" }), ancho: "completo" },
    ],
    valores: { tipo: productoId || estado.productos.length ? "agotado" : "inexistente", cantidad: 1, productoId: productoId ?? "" },
    construir: (contenedor) => {
      // Muestra solo el campo que corresponde al tipo elegido.
      const tipo = contenedor.querySelector("[name=tipo]");
      const actualizar = () => {
        const agotado = tipo.value === "agotado";
        const campoProducto = contenedor.querySelector('[data-campo="productoId"]');
        const campoNombre = contenedor.querySelector('[data-campo="nombre"]');
        campoProducto.hidden = !agotado;
        campoNombre.hidden = agotado;
        campoProducto.querySelector("select").required = agotado;
        campoNombre.querySelector("input").required = !agotado;
      };
      tipo.addEventListener("change", actualizar);
      actualizar();
    },
    recolectar: (datos) => {
      const cuerpo = {
        tipo: datos.tipo,
        cantidad: datos.cantidad,
        proveedorId: datos.proveedorId ? Number(datos.proveedorId) : null,
      };
      if (datos.tipo === "agotado") cuerpo.productoId = Number(datos.productoId);
      else cuerpo.nombre = datos.nombre;
      return cuerpo;
    },
    alGuardar: async (cuerpo) => {
      const faltante = await api.post("faltantes/", cuerpo);
      avisar(`Faltante registrado: ${faltante.nombre} × ${faltante.cantidad}.`);
      if (paginaVisible()) await cargarLista().catch(() => {});
    },
  });
}

async function resolver(ids, boton) {
  const ok = await intentar(
    () => Promise.all(ids.map((id) => api.post(`faltantes/${id}/resolver/`))),
    { cargando: "Marcando como resuelto…", exito: ids.length > 1 ? `${ids.length} faltantes resueltos.` : "Faltante resuelto.", boton },
  );
  if (ok) await cargarLista().catch(() => {});
}

async function eliminar(id, boton) {
  if (!confirmar("¿Eliminar este registro de faltante?")) return;
  const resultado = await intentar(() => api.del(`faltantes/${id}/`), { exito: "Faltante eliminado.", boton });
  if (resultado === null) await cargarLista().catch(() => {});
}

export async function mostrar() {
  const proveedor = $("#missing-filter-provider");
  const elegido = proveedor.value;
  proveedor.innerHTML =
    '<option value="">Todos</option><option value="ninguno">Sin proveedor</option>' + opciones(estado.proveedores, { vacio: null });
  proveedor.value = elegido;
  if (pestana === "compras" && !esAdmin()) pestana = "registros";
  await cambiarPestana(pestana);
}

export function iniciar() {
  $("#new-missing").addEventListener("click", () => abrirRegistroFaltante());
  $("#missing-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    cargarLista().catch(() => {});
  });
  $("#page-faltantes .entity-tabs").addEventListener("click", (e) => {
    const tab = e.target.closest("[data-missing-tab]");
    if (tab) cambiarPestana(tab.dataset.missingTab).catch(() => {});
  });
  $("#missing-list").addEventListener("click", (e) => {
    const resolverUno = e.target.closest("[data-missing-resolve]");
    if (resolverUno) return resolver([Number(resolverUno.dataset.missingResolve)], resolverUno);
    const borrar = e.target.closest("[data-missing-delete]");
    if (borrar) return eliminar(Number(borrar.dataset.missingDelete), borrar);
    const grupo = e.target.closest("[data-group-resolve]");
    if (grupo) resolver(grupos[Number(grupo.dataset.groupResolve)].ids, grupo);
  });
}
