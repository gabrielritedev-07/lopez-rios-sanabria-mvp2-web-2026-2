// Historial de ventas, factura (comprobante), corrección y reembolsos.
import { api } from "../api.js";
import { cargar, estado, porId } from "../estado.js";
import { irA } from "../navegacion.js";
import { esAdmin } from "../sesion.js";
import { $, abrirFormulario, avisar, ejecutar, esc, fecha, intentar, opciones, pesos } from "../ui.js";
import { crearEditorLineas, leerLineas } from "./lineas.js";
import { retomarVenta } from "./venta.js";

let ventas = [];

const unidades = (v) => v.items.reduce((suma, i) => suma + i.cantidad, 0);

function etiquetas(v) {
  const tags = [
    v.estado === "abierta"
      ? '<span class="tag tag--open">Abierta</span>'
      : '<span class="tag tag--closed">Cerrada</span>',
  ];
  if (v.corregida) tags.push('<span class="tag tag--fixed">Corregida</span>');
  if (v.estadoReembolso === "parcial") tags.push('<span class="tag tag--refund">Reembolso parcial</span>');
  if (v.estadoReembolso === "total") tags.push('<span class="tag tag--refund">Reembolso total</span>');
  return `<span class="tags">${tags.join("")}</span>`;
}

function acciones(v) {
  if (v.estado === "abierta") {
    return `<button class="button button--primary" type="button" data-resume="${v.id}">Retomar</button>`;
  }
  const botones = [`<button class="button button--secondary" type="button" data-receipt="${v.id}">Ver factura</button>`];
  if (esAdmin() && v.estadoReembolso === "ninguno") {
    botones.push(`<button class="button button--secondary" type="button" data-fix="${v.id}">Corregir</button>`);
  }
  if (esAdmin() && v.estadoReembolso !== "total") {
    botones.push(`<button class="button button--secondary" type="button" data-refund="${v.id}">Reembolsar</button>`);
  }
  return botones.join("");
}

function render() {
  $("#sales-list").innerHTML =
    ventas
      .map(
        (v) => `<article class="sale-record">
          <div><p class="eyebrow">${esc(v.numero)} · ${esc(fecha(v.fecha))}</p>
            <h2>${unidades(v)} artículos · ${esc(v.metodoPago)} ${etiquetas(v)}</h2>
            <p>${esc(v.clienteNombre || "Mostrador")} · ${v.items.map((i) => esc(i.nombre)).join(", ")}</p></div>
          <div class="sale-record__actions"><strong>${pesos(v.total)}</strong>${acciones(v)}</div>
        </article>`,
      )
      .join("") || '<p class="empty-list">No hay ventas con estos filtros.</p>';
}

async function cargarVentas() {
  const filtros = {
    estado: $("#sales-filter-state").value,
    desde: $("#sales-filter-from").value,
    hasta: $("#sales-filter-to").value,
  };
  ventas = await ejecutar(() => api.get("ventas/", filtros), { cargando: "Cargando ventas…" });
  render();
}

function reemplazarVenta(venta) {
  ventas = ventas.map((v) => (v.id === venta.id ? venta : v));
  render();
}

// ---------------------------------------------------------------------------
// Comprobante / factura
// ---------------------------------------------------------------------------
export function mostrarComprobante(v) {
  const cliente = porId("clientes", v.clienteId);
  const datosCliente = cliente
    ? `<strong>Cliente:</strong> ${esc(cliente.nombre)}${cliente.telefono ? `<br/><strong>Teléfono:</strong> ${esc(cliente.telefono)}` : ""}${cliente.correo ? `<br/><strong>Correo:</strong> ${esc(cliente.correo)}` : ""}`
    : v.clienteNombre
      ? `<strong>Cliente:</strong> ${esc(v.clienteNombre)}`
      : '<strong>Cliente:</strong> Venta de mostrador<br/><span class="receipt__muted">No se asoció un cliente.</span>';

  const filas = v.items
    .map(
      (i) => `<tr><td>${esc(i.nombre)}${i.cantidadReembolsada ? `<br/><small class="receipt__muted">${i.cantidadReembolsada} reembolsada(s)</small>` : ""}</td>
        <td class="receipt__number">${i.cantidad}</td><td class="receipt__number">${pesos(i.precioUnitario)}</td><td class="receipt__number">${pesos(i.subtotal)}</td></tr>`,
    )
    .join("");

  const correccion = v.corregida
    ? `<p class="receipt__flag"><strong>Venta corregida</strong> por ${esc(v.corregidaPor)} · ${esc(fecha(v.corregidaEn))}</p>`
    : "";

  const reembolsos = v.reembolsos.length
    ? `<div class="receipt__refunds"><h3>Reembolsos (${v.estadoReembolso === "total" ? "total" : "parcial"})</h3>
        ${v.reembolsos
          .map(
            (r) => `<p><strong>${esc(fecha(r.fecha))}</strong> · ${esc(r.usuario)} · ${pesos(r.total)}<br/>
              ${r.items.map((i) => `${esc(i.nombre)} × ${i.cantidad} (${i.retornaInventario ? "vuelve al inventario" : "no vuelve al inventario"})`).join(", ")}
              ${r.motivo ? `<br/><span class="receipt__muted">Motivo: ${esc(r.motivo)}</span>` : ""}</p>`,
          )
          .join("")}
        <p><strong>Total reembolsado:</strong> ${pesos(v.totalReembolsado)}</p></div>`
    : "";

  $("#receipt").innerHTML = `
    <div class="receipt__head"><img src="assets/logo-papel-y-luna.png" alt="Logo Papel y Luna"/><div><p class="eyebrow">Comprobante de venta</p><h2>Papel y Luna</h2><p>Papelería y miscelánea</p></div></div>
    ${correccion}
    <div class="receipt__metadata">
      <p><strong>Venta:</strong> ${esc(v.numero)}<br/><strong>Fecha:</strong> ${esc(fecha(v.fecha))}<br/><strong>Estado:</strong> ${esc(v.estado)}<br/><strong>Método de pago:</strong> ${esc(v.metodoPago)}<br/><strong>Atendió:</strong> ${esc(v.cerradaPor || v.creadaPor)}</p>
      <p>${datosCliente}</p>
    </div>
    <div class="table-wrap"><table class="receipt__table"><thead><tr><th>Producto</th><th class="receipt__number">Cant.</th><th class="receipt__number">Precio unitario</th><th class="receipt__number">Importe</th></tr></thead><tbody>${filas}</tbody></table></div>
    <div class="receipt__totals">
      <div><span>Subtotal</span><strong>${pesos(v.subtotal)}</strong></div>
      ${v.descuento ? `<div class="receipt__discount"><span>Descuento ${esc(v.descuento.nombre)}${v.descuento.tipo === "PORCENTAJE" ? ` (${v.descuento.valor} %)` : ""}</span><strong>− ${pesos(v.descuentoMonto)}</strong></div>` : ""}
      <div class="receipt__grand-total"><span>Total pagado</span><strong>${pesos(v.total)}</strong></div>
      <div class="receipt__muted-row"><span>IVA incluido (${v.ivaPorcentaje} %)</span><span>${pesos(v.ivaIncluido)}</span></div>
    </div>
    ${v.metodoPago === "Efectivo" && v.estado === "cerrada" ? `<p class="receipt__payment"><strong>Recibido:</strong> ${pesos(v.valorRecibido)}<br/><strong>Cambio:</strong> ${pesos(v.cambio)}</p>` : ""}
    ${reembolsos}
    <p class="receipt__thanks">Gracias por tu compra.</p>
    <button class="button button--primary print-hidden" id="print-receipt" type="button">Imprimir / Guardar como PDF</button>`;
}

// ---------------------------------------------------------------------------
// Corrección de una venta cerrada (solo administrador)
// ---------------------------------------------------------------------------
function abrirCorreccion(v) {
  const opcionesDescuento =
    (v.descuento ? `<option value="__mantener">Conservar: ${esc(v.descuento.nombre)}</option>` : "") +
    opciones(estado.descuentos, { vacio: "Sin descuento" });
  abrirFormulario({
    titulo: `Corregir ${v.numero}`,
    kicker: "Corrección de venta cerrada",
    nota: `Total actual: ${pesos(v.total)}`,
    textoGuardar: "Guardar corrección",
    campos: [
      { nombre: "clienteId", etiqueta: "Cliente", tipo: "select", opciones: opciones(estado.clientes, { vacio: "Sin cliente (mostrador)" }) },
      { nombre: "metodoPago", etiqueta: "Método de pago", tipo: "select", requerido: true, opciones: ["Efectivo", "Nequi", "Debe"].map((m) => `<option>${m}</option>`).join("") },
      { nombre: "descuento", etiqueta: "Descuento", tipo: "select", opciones: opcionesDescuento },
      { nombre: "valorRecibido", etiqueta: "Valor recibido (solo efectivo)", tipo: "number", min: 0 },
    ],
    valores: {
      clienteId: v.clienteId ?? "",
      metodoPago: v.metodoPago,
      descuento: v.descuento ? "__mantener" : "",
      valorRecibido: v.metodoPago === "Efectivo" ? v.valorRecibido : "",
    },
    construir: (contenedor) => {
      const nota = document.createElement("p");
      nota.className = "dialog-note";
      nota.textContent =
        "La venta conserva su número. El inventario se ajusta solo por la diferencia: si agregas unidades salen del stock y si las quitas vuelven. Los productos que ya estaban conservan su precio original.";
      contenedor.append(nota);
      crearEditorLineas(contenedor, { iniciales: v.items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad })) });
    },
    recolectar: (datos, contenedor) => {
      const cuerpo = {
        items: leerLineas(contenedor),
        clienteId: datos.clienteId ? Number(datos.clienteId) : null,
        metodoPago: datos.metodoPago,
        valorRecibido: datos.metodoPago === "Efectivo" ? datos.valorRecibido : null,
      };
      if (datos.descuento !== "__mantener") cuerpo.descuentoId = datos.descuento ? Number(datos.descuento) : null;
      return cuerpo;
    },
    alGuardar: async (cuerpo) => {
      const corregida = await api.post(`ventas/${v.id}/corregir/`, cuerpo);
      reemplazarVenta(corregida);
      await intentar(() => cargar("productos"));
      avisar(`Venta ${corregida.numero} corregida. Nuevo total: ${pesos(corregida.total)}.`);
    },
  });
}

// ---------------------------------------------------------------------------
// Reembolso parcial o total (solo administrador)
// ---------------------------------------------------------------------------
function abrirReembolso(v) {
  const pendientes = v.items.filter((i) => i.cantidad - i.cantidadReembolsada > 0);
  abrirFormulario({
    titulo: `Reembolsar ${v.numero}`,
    kicker: "Reembolso",
    nota: `Total pagado: ${pesos(v.total)} · ya reembolsado: ${pesos(v.totalReembolsado)}`,
    textoGuardar: "Registrar reembolso",
    campos: [{ nombre: "motivo", etiqueta: "Motivo (opcional)", tipo: "textarea", ancho: "completo" }],
    construir: (contenedor) => {
      const nota = document.createElement("p");
      nota.className = "dialog-note";
      nota.textContent = v.descuento
        ? `El valor se calcula proporcional a lo pagado: respeta el descuento “${v.descuento.nombre}”.`
        : "El valor se calcula con el precio pagado por cada unidad.";
      const caja = document.createElement("div");
      caja.className = "dialog-lines";
      caja.innerHTML = pendientes
        .map((i) => {
          const disponible = i.cantidad - i.cantidadReembolsada;
          return `<div class="dialog-line refund-line" data-producto="${i.productoId}" data-disponible="${disponible}">
            <div class="refund-line__info"><strong>${esc(i.nombre)}</strong><small>Vendidas: ${i.cantidad} · pueden reembolsarse: ${disponible} · ${pesos(i.precioUnitario)} c/u</small></div>
            <label>Cantidad<input type="number" name="reembolso-cantidad" min="0" max="${disponible}" step="1" value="0" /></label>
            <label class="checkbox-label"><input type="checkbox" name="reembolso-retorna" checked /> Vuelve al inventario</label>
          </div>`;
        })
        .join("");

      const todo = document.createElement("button");
      todo.type = "button";
      todo.className = "button button--secondary span-2";
      todo.textContent = "Seleccionar todo (reembolso total)";
      todo.addEventListener("click", () => {
        caja.querySelectorAll(".refund-line").forEach((fila) => {
          fila.querySelector("[name=reembolso-cantidad]").value = fila.dataset.disponible;
        });
      });
      // Orden: nota, productos, botón "todo" y al final el campo de motivo.
      contenedor.prepend(nota, caja, todo);
    },
    recolectar: (datos, contenedor) => {
      const items = [...contenedor.querySelectorAll(".refund-line")]
        .map((fila) => ({
          productoId: Number(fila.dataset.producto),
          cantidad: Number(fila.querySelector("[name=reembolso-cantidad]").value || 0),
          retornaInventario: fila.querySelector("[name=reembolso-retorna]").checked,
          disponible: Number(fila.dataset.disponible),
        }))
        .filter((item) => item.cantidad > 0);
      if (!items.length) throw new Error("Indica la cantidad a reembolsar de al menos un producto.");
      const excedido = items.find((item) => !Number.isInteger(item.cantidad) || item.cantidad > item.disponible);
      if (excedido) throw new Error("Una de las cantidades supera las unidades que se pueden reembolsar.");
      return { motivo: datos.motivo, items: items.map(({ disponible, ...item }) => item) };
    },
    alGuardar: async (cuerpo) => {
      const venta = await api.post(`ventas/${v.id}/reembolsos/`, cuerpo);
      reemplazarVenta(venta);
      await intentar(() => cargar("productos"));
      avisar(`Reembolso registrado por ${pesos(venta.reembolsos[0]?.total)} en la venta ${venta.numero}.`);
    },
  });
}

// ---------------------------------------------------------------------------
export async function mostrar() {
  await cargarVentas();
}

export function iniciar() {
  $("#sales-filters").addEventListener("submit", (e) => {
    e.preventDefault();
    cargarVentas().catch(() => {});
  });
  $("#sales-list").addEventListener("click", (e) => {
    const buscar = (atributo) => {
      const boton = e.target.closest(`[${atributo}]`);
      return boton ? ventas.find((v) => String(v.id) === boton.getAttribute(atributo)) : null;
    };
    const retomar = buscar("data-resume");
    if (retomar) return retomarVenta(retomar);
    const factura = buscar("data-receipt");
    if (factura) {
      mostrarComprobante(factura);
      return irA("comprobante");
    }
    const corregir = buscar("data-fix");
    if (corregir) return abrirCorreccion(corregir);
    const reembolsar = buscar("data-refund");
    if (reembolsar) abrirReembolso(reembolsar);
  });
  document.addEventListener("click", (e) => {
    if (e.target.matches("#print-receipt")) window.print();
  });
}
