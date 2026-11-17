// Editor de líneas de productos reutilizado en compras y en la corrección de ventas.
import { estado, porId } from "../estado.js";
import { $$, esc, opciones } from "../ui.js";

export function crearEditorLineas(contenedor, { iniciales = [], conCosto = false } = {}) {
  const caja = document.createElement("div");
  caja.className = "dialog-lines";
  contenedor.append(caja);

  const textoProducto = (p) => `${p.nombre}${p.seguimientoInventario ? ` · stock ${p.stock}` : ""}`;

  const agregar = (linea = {}) => {
    const fila = document.createElement("div");
    fila.className = conCosto ? "dialog-line dialog-line--cost" : "dialog-line";
    fila.innerHTML = `
      <label>Producto *<select name="linea-producto" required>${opciones(estado.productos, { texto: textoProducto })}</select></label>
      <label>Cantidad *<input name="linea-cantidad" type="number" min="1" step="1" required value="${esc(linea.cantidad ?? 1)}" /></label>
      ${conCosto ? `<label>Costo unitario *<input name="linea-costo" type="number" min="0" step="1" required value="${esc(linea.costo ?? 0)}" /></label>` : ""}
      <button type="button" class="button button--danger" data-quitar-linea aria-label="Quitar producto">×</button>`;
    fila.querySelector("select").value = linea.productoId ?? "";
    caja.append(fila);
  };

  (iniciales.length ? iniciales : [{}]).forEach(agregar);

  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "button button--secondary span-2";
  boton.textContent = "+ Agregar producto";
  boton.addEventListener("click", () => agregar());
  contenedor.append(boton);

  caja.addEventListener("click", (e) => {
    const quitar = e.target.closest("[data-quitar-linea]");
    if (quitar && caja.children.length > 1) quitar.closest(".dialog-line").remove();
  });
  if (conCosto) {
    // Al elegir un producto se propone su último costo de compra.
    caja.addEventListener("change", (e) => {
      if (e.target.name !== "linea-producto") return;
      const producto = porId("productos", e.target.value);
      if (producto) e.target.closest(".dialog-line").querySelector("[name=linea-costo]").value = producto.costo;
    });
  }
}

export function leerLineas(contenedor, { conCosto = false } = {}) {
  const lineas = $$(".dialog-line", contenedor).map((fila) => {
    const linea = {
      productoId: Number(fila.querySelector("[name=linea-producto]").value),
      cantidad: Number(fila.querySelector("[name=linea-cantidad]").value),
    };
    if (conCosto) linea.costo = Number(fila.querySelector("[name=linea-costo]").value);
    return linea;
  });
  if (!lineas.length) throw new Error("Agrega al menos un producto.");
  if (lineas.some((l) => !l.productoId || !Number.isInteger(l.cantidad) || l.cantidad < 1)) {
    throw new Error("Revisa cada producto y su cantidad (mínimo 1).");
  }
  if (conCosto && lineas.some((l) => !Number.isInteger(l.costo) || l.costo < 0)) {
    throw new Error("El costo unitario debe ser un número entero mayor o igual a 0.");
  }
  return lineas;
}
