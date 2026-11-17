// Punto de venta: catálogo, carrito, ventas abiertas, cierre y edición en caliente.
// El carrito vive en memoria (estado.venta). Al guardar o cerrar se envía al backend,
// que valida stock y pago y recalcula todos los totales.
import { api } from "../api.js";
import { IVA_PORCENTAJE } from "../config.js";
import { cargar, estado, porId, reemplazar } from "../estado.js";
import { irA } from "../navegacion.js";
import { $, $$, abrirFormulario, avisar, ejecutar, esc, intentar, opciones, pesos } from "../ui.js";
import { abrirFormularioCliente } from "./entidades.js";
import { abrirRegistroFaltante } from "./faltantes.js";
import { mostrarComprobante } from "./historial.js";

const ICONOS = [
  ["cuaderno", "cuaderno"], ["libreta", "cuaderno"], ["agenda", "cuaderno"],
  ["lápiz", "lapiz"], ["lapiz", "lapiz"], ["lapicero", "lapiz"], ["esfero", "lapiz"],
  ["color", "lapiz"], ["marcador", "lapiz"], ["dulce", "dulce"], ["chocolate", "dulce"],
  ["galleta", "dulce"], ["mecato", "dulce"], ["higiene", "higiene"], ["jabón", "higiene"],
  ["impres", "impresion"], ["copia", "impresion"], ["recarga", "recarga"], ["minuto", "recarga"],
];
let categoriaActiva = "Todas";

// ---------------------------------------------------------------------------
// Carrito
// ---------------------------------------------------------------------------
function nuevaVenta() {
  return { id: null, numero: null, items: [], clienteId: "", metodoPago: "Efectivo", descuentoId: "", valorRecibido: "" };
}

function carrito() {
  estado.venta ??= nuevaVenta();
  return estado.venta;
}

const productoDe = (item) => porId("productos", item.productoId);
// El backend usa el precio ACTUAL del producto al guardar o cerrar; la vista previa también.
const precioDe = (item) => productoDe(item)?.precio ?? item.precio;
const unidades = (v) => v.items.reduce((suma, i) => suma + i.cantidad, 0);

// Vista previa de totales. Los valores definitivos los calcula el backend al cerrar.
function calcular(v) {
  const subtotal = v.items.reduce((suma, i) => suma + precioDe(i) * i.cantidad, 0);
  const descuento = v.descuentoId ? porId("descuentos", v.descuentoId) : null;
  let montoDescuento = 0;
  if (descuento) {
    montoDescuento = descuento.tipo === "PORCENTAJE" ? Math.round((subtotal * descuento.valor) / 100) : descuento.valor;
  }
  const excedido = montoDescuento > subtotal;
  const total = excedido ? 0 : subtotal - montoDescuento;
  const iva = total - Math.round((total * 100) / (100 + IVA_PORCENTAJE));
  return { subtotal, descuento, montoDescuento, excedido, total, iva };
}

// Convierte una venta de la API al formato del carrito.
function desdeApi(venta) {
  return {
    id: venta.id,
    numero: venta.numero,
    items: venta.items.map((i) => ({ productoId: i.productoId, nombre: i.nombre, precio: i.precioUnitario, cantidad: i.cantidad })),
    clienteId: venta.clienteId ?? "",
    metodoPago: venta.metodoPago || "Efectivo",
    descuentoId: venta.descuentoId ?? "",
    valorRecibido: venta.valorRecibido || "",
  };
}

// Cuerpo JSON que se envía al backend: solo ids y cantidades, nunca precios ni totales.
function cuerpoVenta(v) {
  return {
    items: v.items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad })),
    clienteId: v.clienteId ? Number(v.clienteId) : null,
    metodoPago: v.metodoPago,
    descuentoId: v.descuentoId ? Number(v.descuentoId) : null,
    valorRecibido: v.metodoPago === "Efectivo" && v.valorRecibido !== "" ? Number(v.valorRecibido) : null,
  };
}

// ---------------------------------------------------------------------------
// Catálogo
// ---------------------------------------------------------------------------
function iconoDe(producto) {
  const texto = `${producto.nombre} ${producto.categoriaNombre}`.toLowerCase();
  const icono = ICONOS.find(([clave]) => texto.includes(clave))?.[1] || "papel";
  return `assets/productos/${icono}.svg`;
}

function renderFiltros() {
  const nombres = ["Todas", ...new Set(estado.productos.map((p) => p.categoriaNombre))];
  if (!nombres.includes(categoriaActiva)) categoriaActiva = "Todas";
  $("#category-filters").innerHTML = nombres
    .map((n) => `<button type="button" data-category="${esc(n)}" aria-pressed="${n === categoriaActiva}">${esc(n)}</button>`)
    .join("");
}

function renderCatalogo() {
  const texto = $("#sale-search").value.trim().toLowerCase();
  const lista = estado.productos.filter(
    (p) =>
      (categoriaActiva === "Todas" || p.categoriaNombre === categoriaActiva) &&
      `${p.nombre} ${p.codigo || ""}`.toLowerCase().includes(texto),
  );
  $("#product-count").textContent = `${lista.length} productos`;
  const grilla = $("#product-grid");
  grilla.replaceChildren();
  if (!lista.length) {
    grilla.innerHTML = '<p class="empty-list">No hay productos que coincidan.</p>';
    return;
  }
  const plantilla = $("#product-template");
  for (const p of lista) {
    const tarjeta = plantilla.content.cloneNode(true);
    tarjeta.querySelector("img").src = iconoDe(p);
    tarjeta.querySelector(".product-card__category").textContent = p.categoriaNombre;
    tarjeta.querySelector("h3").textContent = p.nombre;
    tarjeta.querySelector(".product-card__description").textContent = p.seguimientoInventario
      ? `${p.stock} en stock${p.codigo ? ` · ${p.codigo}` : ""}`
      : p.codigo || "Sin control de inventario";
    tarjeta.querySelector(".product-card__footer strong").textContent = pesos(p.precio);
    const agotado = p.seguimientoInventario && p.stock < 1;
    const agregar = tarjeta.querySelector(".add-product");
    agregar.dataset.id = p.id;
    agregar.disabled = agotado;
    agregar.textContent = agotado ? "Sin stock" : "Agregar";
    const faltante = tarjeta.querySelector(".report-missing");
    faltante.dataset.id = p.id;
    faltante.hidden = !agotado;
    tarjeta.querySelector(".edit-sale-product").dataset.id = p.id;
    grilla.append(tarjeta);
  }
}

// ---------------------------------------------------------------------------
// Carrito: pintar y validar
// ---------------------------------------------------------------------------
function renderSelectores() {
  const v = carrito();
  $("#sale-client").innerHTML = opciones(estado.clientes, {
    vacio: "Venta de mostrador — sin cliente",
    texto: (c) => `${c.nombre}${c.telefono ? ` · ${c.telefono}` : ""}`,
  });
  $("#sale-client").value = v.clienteId;
  $("#sale-discount-select").innerHTML = opciones(estado.descuentos, {
    vacio: "Sin descuento",
    texto: (d) => `${d.nombre} (${d.tipo === "PORCENTAJE" ? `${d.valor} %` : pesos(d.valor)})`,
  });
  if (v.descuentoId && !porId("descuentos", v.descuentoId)) v.descuentoId = "";
  $("#sale-discount-select").value = v.descuentoId;
}

function renderResumenCliente() {
  const cliente = porId("clientes", carrito().clienteId);
  $("#client-summary").textContent = cliente
    ? [cliente.nombre, cliente.telefono, cliente.correo].filter(Boolean).join(" · ")
    : "Venta de mostrador. Para pago Debe es obligatorio elegir un cliente.";
}

function renderCarrito() {
  const v = carrito();
  const c = calcular(v);
  $("#cart-title").textContent = v.id ? "Venta abierta" : "Venta actual";
  $("#sale-id").textContent = v.id ? `Venta ${v.numero} · guardada` : "Venta nueva · sin guardar";
  $("#cart-lines").innerHTML = v.items
    .map((i) => {
      const precio = precioDe(i);
      return `<article class="cart-line"><div><h3>${esc(productoDe(i)?.nombre ?? i.nombre)}</h3><p>${pesos(precio)} c/u</p>
        <div class="quantity-controls"><button type="button" data-action="minus" data-id="${i.productoId}" aria-label="Quitar uno">−</button><input data-qty="${i.productoId}" type="number" min="1" value="${i.cantidad}" aria-label="Cantidad"/><button type="button" data-action="plus" data-id="${i.productoId}" aria-label="Agregar uno">+</button><button type="button" data-action="remove" data-id="${i.productoId}" class="remove-button" aria-label="Quitar producto">×</button></div></div>
        <strong>${pesos(precio * i.cantidad)}</strong></article>`;
    })
    .join("");
  $("#cart-empty").hidden = v.items.length > 0;
  $("#cart-count").textContent = `${unidades(v)} artículos`;
  $("#sale-subtotal").textContent = pesos(c.subtotal);
  $("#discount-row").hidden = !c.descuento;
  $("#discount-label").textContent = c.descuento ? `Descuento ${c.descuento.nombre}` : "Descuento";
  $("#sale-discount").textContent = `− ${pesos(c.montoDescuento)}`;
  $("#sale-total").textContent = pesos(c.total);
  $("#sale-iva-label").textContent = `IVA incluido (${IVA_PORCENTAJE} %)`;
  $("#sale-iva").textContent = pesos(c.iva);
  $("#payment-method").value = v.metodoPago;
  $("#cash-fields").hidden = v.metodoPago !== "Efectivo";
  $("#cash-received").value = v.valorRecibido;
  renderResumenCliente();
  validar();
}

function validar() {
  const v = carrito();
  const c = calcular(v);
  const recibido = Number(v.valorRecibido || 0);
  const sinStock = v.items.filter((i) => {
    const p = productoDe(i);
    return p?.seguimientoInventario && i.cantidad > p.stock;
  });
  let mensaje = "";
  let valida = v.items.length > 0;
  if (sinStock.length) {
    valida = false;
    mensaje = `Stock insuficiente: ${sinStock.map((i) => `${i.nombre} (disponible: ${productoDe(i).stock})`).join(", ")}.`;
  } else if (c.excedido) {
    valida = false;
    mensaje = "El descuento supera el subtotal de la venta.";
  } else if (v.items.length && v.metodoPago === "Debe" && !v.clienteId) {
    valida = false;
    mensaje = "Selecciona un cliente para las ventas con pago Debe.";
  } else if (v.items.length && v.metodoPago === "Efectivo" && recibido < c.total) {
    valida = false;
    mensaje = v.valorRecibido === "" ? "Indica el valor recibido en efectivo." : `Faltan ${pesos(c.total - recibido)}.`;
  }
  $("#sale-error").textContent = mensaje;
  $("#change-note").textContent =
    v.metodoPago === "Efectivo" && v.items.length && recibido >= c.total ? `Cambio: ${pesos(recibido - c.total)}` : "";
  $("#close-sale").disabled = !valida;
  $("#save-open").disabled = v.items.length === 0;
}

// ---------------------------------------------------------------------------
// Acciones del carrito
// ---------------------------------------------------------------------------
function agregarProducto(id) {
  const p = porId("productos", id);
  if (!p) return;
  const v = carrito();
  const linea = v.items.find((i) => i.productoId === p.id);
  const cantidad = (linea?.cantidad ?? 0) + 1;
  if (p.seguimientoInventario && cantidad > p.stock) {
    avisar(`Stock insuficiente de ${p.nombre} (disponible: ${p.stock}).`, { error: true });
    return;
  }
  if (linea) linea.cantidad = cantidad;
  else v.items.push({ productoId: p.id, nombre: p.nombre, precio: p.precio, cantidad: 1 });
  renderCarrito();
}

function cambiarCantidad(productoId, cantidad) {
  const v = carrito();
  const linea = v.items.find((i) => i.productoId === productoId);
  if (!linea) return;
  const p = productoDe(linea);
  if (cantidad <= 0) {
    v.items = v.items.filter((i) => i !== linea);
  } else if (p?.seguimientoInventario && cantidad > p.stock) {
    avisar(`Stock disponible de ${p.nombre}: ${p.stock}.`, { error: true });
  } else {
    linea.cantidad = cantidad;
  }
  renderCarrito();
}

async function guardarAbierta(boton) {
  const v = carrito();
  if (!v.items.length) return;
  const venta = await intentar(
    () => (v.id ? api.patch(`ventas/${v.id}/`, cuerpoVenta(v)) : api.post("ventas/", cuerpoVenta(v))),
    { cargando: "Guardando venta abierta…", boton },
  );
  if (!venta) return;
  estado.venta = null;
  renderCarrito();
  avisar(`Venta ${venta.numero} guardada como abierta. Puedes retomarla desde Ventas.`);
}

async function cerrarVenta(boton) {
  const v = carrito();
  const venta = await intentar(
    () => (v.id ? api.post(`ventas/${v.id}/cerrar/`, cuerpoVenta(v)) : api.post("ventas/", { ...cuerpoVenta(v), cerrar: true })),
    { cargando: "Cerrando venta…", boton },
  );
  if (!venta) {
    validar();
    return;
  }
  estado.venta = null;
  await intentar(() => cargar("productos"));
  renderCatalogo();
  renderCarrito();
  mostrarComprobante(venta);
  await irA("comprobante");
  avisar(`Venta ${venta.numero} cerrada por ${pesos(venta.total)}.`);
}

// Edición en caliente: el cajero corrige nombre, código, categoría o precio sin salir de la venta.
function editarEnCaliente(id) {
  const p = porId("productos", id);
  if (!p) return;
  abrirFormulario({
    titulo: "Editar producto",
    kicker: "Edición desde la venta",
    nota: "Solo cambia datos de venta. El stock y el costo se gestionan en Productos y Compras.",
    campos: [
      { nombre: "nombre", etiqueta: "Nombre", requerido: true, ancho: "completo" },
      { nombre: "categoriaId", etiqueta: "Categoría", tipo: "select", requerido: true, opciones: opciones(estado.categorias) },
      { nombre: "precio", etiqueta: "Precio de venta (IVA incluido)", tipo: "number", min: 0, requerido: true },
      { nombre: "codigo", etiqueta: "Código" },
    ],
    valores: p,
    alGuardar: async (datos) => {
      const actualizado = await api.patch(`productos/${p.id}/edicion-rapida/`, {
        ...datos,
        categoriaId: Number(datos.categoriaId),
      });
      reemplazar("productos", actualizado);
      for (const linea of carrito().items) {
        if (linea.productoId === actualizado.id) {
          linea.nombre = actualizado.nombre;
          linea.precio = actualizado.precio;
        }
      }
      renderFiltros();
      renderCatalogo();
      renderCarrito();
      avisar(`Producto “${actualizado.nombre}” actualizado.`);
    },
  });
}

// La usa el historial para retomar una venta abierta.
export async function retomarVenta(venta) {
  estado.venta = desdeApi(venta);
  await irA("venta");
  avisar(`Venta ${venta.numero} retomada.`);
}

// ---------------------------------------------------------------------------
// Ciclo de vida del módulo
// ---------------------------------------------------------------------------
export async function mostrar() {
  // Refresca productos para ver el stock actualizado por otros usuarios.
  await ejecutar(() => cargar("productos"), { cargando: "Actualizando catálogo…" }).catch(() => {});
  renderFiltros();
  renderCatalogo();
  renderSelectores();
  renderCarrito();
}

// Pinta de nuevo los selectores cuando otro módulo cambia clientes o descuentos.
export function refrescarSelectores() {
  renderSelectores();
  renderCarrito();
}

export function iniciar() {
  $("#product-grid").addEventListener("click", (e) => {
    const agregar = e.target.closest(".add-product");
    if (agregar) return agregarProducto(Number(agregar.dataset.id));
    const editar = e.target.closest(".edit-sale-product");
    if (editar) return editarEnCaliente(Number(editar.dataset.id));
    const faltante = e.target.closest(".report-missing");
    if (faltante) abrirRegistroFaltante({ productoId: Number(faltante.dataset.id) });
  });
  $("#category-filters").addEventListener("click", (e) => {
    const boton = e.target.closest("[data-category]");
    if (!boton) return;
    categoriaActiva = boton.dataset.category;
    $$("#category-filters button").forEach((b) => b.setAttribute("aria-pressed", String(b === boton)));
    renderCatalogo();
  });
  $("#sale-search").addEventListener("input", renderCatalogo);

  $("#cart-lines").addEventListener("click", (e) => {
    const boton = e.target.closest("[data-action]");
    if (!boton) return;
    const id = Number(boton.dataset.id);
    const linea = carrito().items.find((i) => i.productoId === id);
    if (!linea) return;
    const accion = boton.dataset.action;
    cambiarCantidad(id, accion === "plus" ? linea.cantidad + 1 : accion === "minus" ? linea.cantidad - 1 : 0);
  });
  $("#cart-lines").addEventListener("change", (e) => {
    if (!e.target.matches("[data-qty]")) return;
    const cantidad = Math.floor(Number(e.target.value));
    const id = Number(e.target.dataset.qty);
    // Se repinta en el siguiente ciclo: el evento "change" llega mientras el campo pierde el foco
    // y reemplazar el HTML en ese instante provoca un error en el navegador.
    setTimeout(() => {
      if (!Number.isFinite(cantidad) || cantidad < 1) renderCarrito();
      else cambiarCantidad(id, cantidad);
    }, 0);
  });

  $("#sale-client").addEventListener("change", (e) => {
    carrito().clienteId = e.target.value;
    renderResumenCliente();
    validar();
  });
  $("#sale-discount-select").addEventListener("change", (e) => {
    carrito().descuentoId = e.target.value;
    renderCarrito();
  });
  $("#payment-method").addEventListener("change", (e) => {
    carrito().metodoPago = e.target.value;
    renderCarrito();
  });
  $("#cash-received").addEventListener("input", (e) => {
    carrito().valorRecibido = e.target.value;
    validar();
  });

  $("#save-open").addEventListener("click", (e) => guardarAbierta(e.currentTarget));
  $("#close-sale").addEventListener("click", (e) => cerrarVenta(e.currentTarget));
  $("#new-sale").addEventListener("click", () => {
    if (carrito().items.length && !carrito().id && !window.confirm("¿Descartar la venta actual sin guardar?")) return;
    estado.venta = null;
    renderCarrito();
  });
  $("#new-sale-client").addEventListener("click", () =>
    abrirFormularioCliente((cliente) => {
      carrito().clienteId = String(cliente.id);
      renderSelectores();
      renderCarrito();
    }),
  );
  $("#sale-missing").addEventListener("click", () => abrirRegistroFaltante());
}
