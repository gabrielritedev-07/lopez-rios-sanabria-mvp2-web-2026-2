// Catálogo de descuentos (solo administrador). El cajero solo los aplica desde el punto de venta.
import { api } from "../api.js";
import { cargar, estado, porId, reemplazar } from "../estado.js";
import { $, abrirFormulario, avisar, confirmar, ejecutar, esc, intentar, pesos } from "../ui.js";

const alCambiar = new Set();
export function suscribirDescuentos(callback) {
  alCambiar.add(callback);
}
const notificar = () => alCambiar.forEach((cb) => cb());

const valorLegible = (d) => (d.tipo === "PORCENTAJE" ? `${d.valor} %` : pesos(d.valor));

function render() {
  $("#discounts-table").innerHTML =
    estado.descuentos
      .map(
        (d) => `<tr>
          <td><strong>${esc(d.nombre)}</strong></td>
          <td>${esc(d.tipoNombre)}</td>
          <td>${valorLegible(d)}</td>
          <td><div class="table-actions"><button type="button" data-discount-edit="${d.id}">Editar</button><button type="button" class="text-danger" data-discount-delete="${d.id}">Eliminar</button></div></td>
        </tr>`,
      )
      .join("") || '<tr><td colspan="4" class="table-empty">Aún no hay descuentos.</td></tr>';
}

function abrirFormularioDescuento(descuento = null) {
  abrirFormulario({
    titulo: descuento ? "Editar descuento" : "Nuevo descuento",
    kicker: "Promociones",
    campos: [
      { nombre: "nombre", etiqueta: "Nombre", requerido: true, ancho: "completo" },
      {
        nombre: "tipo", etiqueta: "Tipo", tipo: "select", requerido: true,
        opciones: '<option value="PORCENTAJE">Porcentaje</option><option value="VALOR_FIJO">Valor fijo</option>',
      },
      { nombre: "valor", etiqueta: "Valor", tipo: "number", min: 1, requerido: true, ayuda: "Porcentaje: de 1 a 100. Valor fijo: pesos." },
    ],
    valores: descuento ?? { tipo: "PORCENTAJE" },
    alGuardar: async (datos) => {
      const guardado = descuento
        ? await api.patch(`descuentos/${descuento.id}/`, datos)
        : await api.post("descuentos/", datos);
      reemplazar("descuentos", guardado);
      render();
      notificar();
      avisar(`Descuento “${guardado.nombre}” guardado.`);
    },
  });
}

async function eliminar(id, boton) {
  const d = porId("descuentos", id);
  if (!d || !confirmar(`¿Eliminar el descuento “${d.nombre}”? Las ventas que ya lo usaron no cambian.`)) return;
  const resultado = await intentar(() => api.del(`descuentos/${id}/`), { exito: "Descuento eliminado.", boton });
  if (resultado === null) {
    estado.descuentos = estado.descuentos.filter((x) => x.id !== d.id);
    render();
    notificar();
  }
}

export async function mostrar() {
  await ejecutar(() => cargar("descuentos"), { cargando: "Cargando descuentos…" });
  render();
}

export function iniciar() {
  $("#new-discount").addEventListener("click", () => abrirFormularioDescuento());
  $("#discounts-table").addEventListener("click", (e) => {
    const editar = e.target.closest("[data-discount-edit]");
    if (editar) return abrirFormularioDescuento(porId("descuentos", editar.dataset.discountEdit));
    const borrar = e.target.closest("[data-discount-delete]");
    if (borrar) eliminar(Number(borrar.dataset.discountDelete), borrar);
  });
}
