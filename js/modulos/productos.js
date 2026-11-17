// Productos: consulta para ambos roles; crear, editar y eliminar solo administrador.
import { api } from "../api.js";
import { cargar, estado, porId, reemplazar } from "../estado.js";
import { esAdmin } from "../sesion.js";
import { $, abrirFormulario, avisar, confirmar, ejecutar, esc, intentar, opciones, pesos } from "../ui.js";

function render() {
  const texto = $("#product-search").value.trim().toLowerCase();
  const filas = estado.productos.filter((p) =>
    `${p.nombre} ${p.categoriaNombre} ${p.codigo || ""}`.toLowerCase().includes(texto),
  );
  $("#products-table").innerHTML =
    filas
      .map(
        (p) => `<tr>
          <td><strong>${esc(p.nombre)}</strong><small>${esc(p.codigo || "Sin código")}</small></td>
          <td>${esc(p.categoriaNombre)}</td>
          <td>${pesos(p.costo)}</td>
          <td>${pesos(p.precio)}</td>
          <td>${p.seguimientoInventario ? `${p.stock} unidades` : "No aplica"}</td>
          <td>${esAdmin() ? `<div class="table-actions"><button type="button" data-product-edit="${p.id}">Editar</button><button type="button" data-product-delete="${p.id}" class="text-danger">Eliminar</button></div>` : ""}</td>
        </tr>`,
      )
      .join("") || '<tr><td colspan="6" class="table-empty">No hay productos.</td></tr>';
}

function abrirFormularioProducto(producto = null) {
  if (!estado.categorias.length) {
    avisar("Primero crea una categoría en Entidades.", { error: true });
    return;
  }
  abrirFormulario({
    titulo: producto ? "Editar producto" : "Nuevo producto",
    kicker: "Catálogo",
    nota: producto ? `ID ${producto.id}` : "",
    campos: [
      { nombre: "nombre", etiqueta: "Nombre", requerido: true, ancho: "completo" },
      { nombre: "categoriaId", etiqueta: "Categoría", tipo: "select", requerido: true, opciones: opciones(estado.categorias) },
      { nombre: "codigo", etiqueta: "Código", ayuda: "Opcional; no se puede repetir." },
      { nombre: "precio", etiqueta: "Precio de venta", tipo: "number", min: 0, requerido: true, ayuda: "Incluye IVA." },
      { nombre: "costo", etiqueta: "Costo", tipo: "number", min: 0, ayuda: "Se actualiza con cada compra." },
      { nombre: "seguimientoInventario", etiqueta: "Llevar inventario", tipo: "checkbox" },
      { nombre: "stock", etiqueta: "Stock", tipo: "number", min: 0 },
    ],
    valores: producto ?? { costo: 0, stock: 0, seguimientoInventario: true },
    alGuardar: async (datos) => {
      const cuerpo = {
        ...datos,
        categoriaId: Number(datos.categoriaId),
        costo: datos.costo ?? 0,
        stock: datos.stock ?? 0,
      };
      const guardado = producto
        ? await api.patch(`productos/${producto.id}/`, cuerpo)
        : await api.post("productos/", cuerpo);
      reemplazar("productos", guardado);
      render();
      avisar(`Producto “${guardado.nombre}” guardado.`);
    },
  });
}

async function eliminarProducto(id, boton) {
  const p = porId("productos", id);
  if (!p || !confirmar(`¿Eliminar “${p.nombre}”?`)) return;
  const ok = await intentar(() => api.del(`productos/${id}/`), { exito: `Producto “${p.nombre}” eliminado.`, boton });
  if (ok === null) {
    estado.productos = estado.productos.filter((x) => x.id !== p.id);
    render();
  }
}

export async function mostrar() {
  await ejecutar(() => cargar("productos", "categorias"), { cargando: "Cargando productos…" });
  render();
}

export function iniciar() {
  $("#product-search").addEventListener("input", render);
  $("#new-product").addEventListener("click", () => abrirFormularioProducto());
  $("#products-table").addEventListener("click", (e) => {
    const editar = e.target.closest("[data-product-edit]");
    if (editar) return abrirFormularioProducto(porId("productos", editar.dataset.productEdit));
    const eliminar = e.target.closest("[data-product-delete]");
    if (eliminar) eliminarProducto(Number(eliminar.dataset.productDelete), eliminar);
  });
}
