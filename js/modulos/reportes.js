// Reportes por rango de fechas (solo administrador).
import { api } from "../api.js";
import { $, dia, ejecutar, esc, hoyISO, pesos } from "../ui.js";

const tarjeta = (titulo, valor, detalle = "", principal = false) =>
  `<div class="report-card${principal ? " report-card--main" : ""}"><span>${esc(titulo)}</span><strong>${valor}</strong>${detalle ? `<small>${esc(detalle)}</small>` : ""}</div>`;

const vacio = (texto) => `<p class="empty-list">${esc(texto)}</p>`;

function renderVentas(r) {
  $("#report-sales").innerHTML = [
    tarjeta("Total vendido", pesos(r.totalVendido), `${r.cantidadVentas} venta(s) cerradas`, true),
    tarjeta("Total neto", pesos(r.totalNeto), "Total vendido menos reembolsos"),
    tarjeta("Descuentos", pesos(r.descuentos)),
    tarjeta("Reembolsos", pesos(r.totalReembolsado)),
    tarjeta("IVA incluido", pesos(r.ivaIncluido)),
    tarjeta("Ticket promedio", pesos(r.ticketPromedio)),
  ].join("");
  const chips = [
    ...r.porMetodoPago.map((m) => `<span><strong>${esc(m.metodoPago)}:</strong> ${pesos(m.total)} (${m.cantidad})</span>`),
    ...(r.porDia.length > 1 ? r.porDia.map((d) => `<span>${esc(dia(d.fecha))}: ${pesos(d.total)} (${d.cantidad})</span>`) : []),
  ];
  let desglose = $("#report-breakdown");
  if (!desglose) {
    desglose = document.createElement("div");
    desglose.id = "report-breakdown";
    desglose.className = "report-breakdown";
    $("#report-sales").after(desglose);
  }
  desglose.innerHTML = chips.join("");
}

function renderProductos(r) {
  $("#report-products").innerHTML = r.productos.length
    ? `<div class="table-wrap"><table class="report-table"><thead><tr><th>#</th><th>Producto</th><th class="num">Unidades</th><th class="num">Ingresos</th></tr></thead><tbody>
      ${r.productos
        .map(
          (p) => `<tr><td>${p.posicion}</td><td><strong>${esc(p.nombre)}</strong><small>${p.ventas} venta(s)${p.unidadesReembolsadas ? ` · ${p.unidadesReembolsadas} reembolsada(s)` : ""}</small></td><td class="num">${p.unidadesVendidas}</td><td class="num">${pesos(p.ingresos)}</td></tr>`,
        )
        .join("")}</tbody></table></div>`
    : vacio("No hubo ventas cerradas en este rango.");
}

function renderCompras(r) {
  $("#report-purchases").innerHTML = r.compras.length
    ? `<p class="input-note"><strong>${r.cantidadCompras} compra(s) por ${pesos(r.totalComprado)}</strong> · ${r.porProveedor.map((p) => `${esc(p.proveedorNombre)}: ${pesos(p.total)}`).join(" · ")}</p>
      <div class="table-wrap"><table class="report-table"><thead><tr><th>Compra</th><th>Proveedor</th><th class="num">Total</th></tr></thead><tbody>
      ${r.compras.map((c) => `<tr><td><strong>${esc(c.numero)}</strong><small>${esc(dia(c.fecha))}</small></td><td>${esc(c.proveedorNombre)}</td><td class="num">${pesos(c.total)}</td></tr>`).join("")}
      </tbody></table></div>`
    : vacio("No se registraron compras en este rango.");
}

function renderFaltantes(r) {
  $("#report-missing").innerHTML = r.faltantes.length
    ? `<div class="table-wrap"><table class="report-table"><thead><tr><th>#</th><th>Producto</th><th class="num">Solicitudes</th><th class="num">Cantidad pedida</th><th class="num">Pendientes</th><th>Tipo</th></tr></thead><tbody>
      ${r.faltantes
        .map(
          (f) => `<tr><td>${f.posicion}</td><td><strong>${esc(f.nombre)}</strong><small>${f.productoId ? "En catálogo" : esc(f.nombreNormalizado)}</small></td><td class="num">${f.solicitudes}</td><td class="num">${f.cantidadTotal}</td><td class="num">${f.pendientes}</td><td>${esc(f.tipos.join(", "))}</td></tr>`,
        )
        .join("")}</tbody></table></div>`
    : vacio("No se registraron faltantes en este rango.");
}

async function generar() {
  const rango = { desde: $("#report-from").value, hasta: $("#report-to").value };
  const [ventas, productos, compras, faltantes] = await ejecutar(
    () =>
      Promise.all([
        api.get("reportes/ventas/", rango),
        api.get("reportes/productos-mas-vendidos/", { ...rango, limite: 10 }),
        api.get("reportes/compras/", rango),
        api.get("reportes/faltantes-frecuentes/", { ...rango, limite: 10 }),
      ]),
    { cargando: "Generando reportes…" },
  );
  renderVentas(ventas);
  renderProductos(productos);
  renderCompras(compras);
  renderFaltantes(faltantes);
}

function fijarRango(tipo) {
  const hoy = hoyISO();
  let desde = hoy;
  if (tipo === "7") desde = hoyISO(-6);
  if (tipo === "mes") desde = `${hoy.slice(0, 8)}01`;
  $("#report-from").value = desde;
  $("#report-to").value = hoy;
}

export async function mostrar() {
  if (!$("#report-from").value) fijarRango("hoy");
  await generar();
}

export function iniciar() {
  $("#report-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!e.target.reportValidity()) return;
    generar().catch(() => {});
  });
  $("#report-filters").addEventListener("click", (e) => {
    const rapido = e.target.closest("[data-report-range]");
    if (!rapido) return;
    fijarRango(rapido.dataset.reportRange);
    generar().catch(() => {});
  });
}
