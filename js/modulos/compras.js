// Compras a proveedores (solo administrador). Al registrar, el backend suma stock
// y actualiza el costo de cada producto en una sola transacción.
import { api } from "../api.js";
import { cargar, estado } from "../estado.js";
import { $, abrirFormulario, avisar, dia, ejecutar, esc, hoyISO, intentar, opciones, pesos } from "../ui.js";
import { crearEditorLineas, leerLineas } from "./lineas.js";

let compras = [];

function render() {
  $("#purchases-list").innerHTML =
    compras
      .map(
        (c) => `<article class="sale-record">
          <div><p class="eyebrow">${esc(c.numero)} · ${esc(dia(c.fecha))} · registró ${esc(c.registradaPor)}</p>
            <h2>${esc(c.proveedorNombre)}</h2>
            <p>${c.items.map((i) => `${esc(i.nombre)} × ${i.cantidad} (${pesos(i.costoUnitario)} c/u)`).join(", ")}</p></div>
          <div class="sale-record__actions"><strong>${pesos(c.total)}</strong></div>
        </article>`,
      )
      .join("") || '<p class="empty-list">No hay compras con estos filtros.</p>';
}

async function cargarCompras() {
  const filtros = {
    proveedor: $("#purchases-filter-provider").value,
    desde: $("#purchases-filter-from").value,
    hasta: $("#purchases-filter-to").value,
  };
  compras = await ejecutar(() => api.get("compras/", filtros), { cargando: "Cargando compras…" });
  render();
}

function abrirNuevaCompra() {
  if (!estado.proveedores.length) {
    avisar("Primero crea un proveedor en Entidades.", { error: true });
    return;
  }
  if (!estado.productos.length) {
    avisar("Primero crea productos en el catálogo.", { error: true });
    return;
  }
  abrirFormulario({
    titulo: "Registrar compra",
    kicker: "Abastecimiento",
    textoGuardar: "Registrar compra",
    campos: [
      { nombre: "proveedorId", etiqueta: "Proveedor", tipo: "select", requerido: true, opciones: opciones(estado.proveedores) },
      { nombre: "fecha", etiqueta: "Fecha", tipo: "date", requerido: true, max: hoyISO() },
    ],
    valores: { fecha: hoyISO() },
    construir: (contenedor) => crearEditorLineas(contenedor, { conCosto: true }),
    recolectar: (datos, contenedor) => {
      const items = leerLineas(contenedor, { conCosto: true });
      const ids = items.map((i) => i.productoId);
      if (new Set(ids).size !== ids.length) throw new Error("Cada producto debe aparecer una sola vez en la compra.");
      return { proveedorId: Number(datos.proveedorId), fecha: datos.fecha, items };
    },
    alGuardar: async (cuerpo) => {
      const compra = await api.post("compras/", cuerpo);
      compras = [compra, ...compras];
      render();
      await intentar(() => cargar("productos"));
      avisar(`Compra ${compra.numero} registrada por ${pesos(compra.total)}. Inventario actualizado.`);
    },
  });
}

export async function mostrar() {
  await ejecutar(() => cargar("proveedores", "productos"), { cargando: "Cargando…" });
  const filtro = $("#purchases-filter-provider");
  const elegido = filtro.value;
  filtro.innerHTML = opciones(estado.proveedores, { vacio: "Todos" });
  filtro.value = elegido;
  await cargarCompras();
}

export function iniciar() {
  $("#new-purchase").addEventListener("click", abrirNuevaCompra);
  $("#purchases-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    cargarCompras().catch(() => {});
  });
}
