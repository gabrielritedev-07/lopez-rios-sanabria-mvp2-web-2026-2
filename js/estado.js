// Estado en memoria de la sesión actual. Es solo una copia de lo que respondió la API
// para pintar la interfaz; la fuente de verdad siempre es el backend (PostgreSQL).
import { api } from "./api.js";

export const estado = {
  productos: [],
  categorias: [],
  clientes: [],
  proveedores: [],
  descuentos: [],
  venta: null, // venta en curso en el punto de venta
};

const RUTAS = {
  productos: "productos/",
  categorias: "categorias/",
  clientes: "clientes/",
  proveedores: "proveedores/",
  descuentos: "descuentos/",
};

// Recarga desde la API uno o varios catálogos en paralelo.
export async function cargar(...nombres) {
  const respuestas = await Promise.all(nombres.map((nombre) => api.get(RUTAS[nombre])));
  nombres.forEach((nombre, i) => {
    estado[nombre] = respuestas[i];
  });
}

export const porId = (lista, id) => estado[lista].find((x) => String(x.id) === String(id));

export function reemplazar(lista, registro) {
  const existe = estado[lista].some((x) => x.id === registro.id);
  estado[lista] = existe
    ? estado[lista].map((x) => (x.id === registro.id ? registro : x))
    : [...estado[lista], registro];
}

export function limpiarEstado() {
  for (const clave of Object.keys(RUTAS)) estado[clave] = [];
  estado.venta = null;
}
