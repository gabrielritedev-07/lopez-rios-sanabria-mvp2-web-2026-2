// Navegación entre pantallas (secciones .view) sin recargar la página.
import { esAdmin } from "./sesion.js";
import { $$, avisar } from "./ui.js";

const paginas = {};
export const PAGINAS_ADMIN = new Set(["compras", "descuentos", "reportes"]);

export function registrarPagina(nombre, modulo) {
  paginas[nombre] = modulo;
}

export async function irA(nombre) {
  if (PAGINAS_ADMIN.has(nombre) && !esAdmin()) {
    avisar("Esta sección solo está disponible para el administrador.", { error: true });
    return;
  }
  $$(".view").forEach((vista) => vista.classList.toggle("is-active", vista.id === `page-${nombre}`));
  $$(".nav-link[data-page]").forEach((boton) => boton.classList.toggle("is-active", boton.dataset.page === nombre));
  window.scrollTo(0, 0);
  try {
    await paginas[nombre]?.mostrar?.();
  } catch (error) {
    avisar(error.message || "No se pudo cargar la sección.", { error: true });
  }
}
