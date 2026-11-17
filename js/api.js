// apiClient: única puerta de salida del frontend hacia el backend Django.
// - Envía y recibe JSON.
// - Adjunta "Authorization: Bearer <token>" cuando hay sesión.
// - Si el token vence (401), intenta renovarlo UNA vez con el refresh token;
//   si no se puede, cierra la sesión y avisa a la aplicación para volver al login.
// - Convierte los errores del backend ({detail, errores}) en mensajes legibles.
import { API_URL } from "./config.js";
import { actualizarSesion, borrarSesion, leerSesion } from "./sesion.js";

export class ApiError extends Error {
  constructor(mensaje, { status = 0, codigo = null, errores = null } = {}) {
    super(mensaje);
    this.name = "ApiError";
    this.status = status;
    this.codigo = codigo;
    this.errores = errores;
  }
}

// Nombres legibles de los campos que devuelve la API en los errores de validación.
const ETIQUETAS = {
  nombre: "Nombre", categoriaId: "Categoría", precio: "Precio", costo: "Costo", stock: "Stock",
  codigo: "Código", telefono: "Teléfono", correo: "Correo", tipo: "Tipo", valor: "Valor",
  items: "Productos", clienteId: "Cliente", metodoPago: "Método de pago", descuentoId: "Descuento",
  valorRecibido: "Valor recibido", proveedorId: "Proveedor", fecha: "Fecha", cantidad: "Cantidad",
  productoId: "Producto", username: "Usuario", password: "Contraseña", desde: "Desde",
  hasta: "Hasta", limite: "Límite", motivo: "Motivo", estado: "Estado",
};

let alExpirarSesion = () => {};
export function alCerrarSesionPorVencimiento(callback) {
  alExpirarSesion = callback;
}

function construirUrl(ruta, consulta) {
  const url = new URL(ruta.replace(/^\/+/, ""), API_URL);
  for (const [clave, valor] of Object.entries(consulta || {})) {
    if (valor !== undefined && valor !== null && valor !== "") url.searchParams.set(clave, valor);
  }
  return url;
}

// Busca el primer mensaje dentro de {"errores": {...}} (puede venir anidado en listas).
function primerError(errores, campo = "") {
  if (Array.isArray(errores)) {
    for (const item of errores) {
      const encontrado = primerError(item, campo);
      if (encontrado) return encontrado;
    }
    return null;
  }
  if (errores && typeof errores === "object") {
    for (const [clave, valor] of Object.entries(errores)) {
      const encontrado = primerError(valor, clave === "non_field_errors" ? campo : clave);
      if (encontrado) return encontrado;
    }
    return null;
  }
  return errores ? { campo, mensaje: String(errores) } : null;
}

function mensajeDeError(datos, status) {
  const error = primerError(datos?.errores);
  if (error) {
    const etiqueta = ETIQUETAS[error.campo];
    return etiqueta ? `${etiqueta}: ${error.mensaje}` : error.mensaje;
  }
  if (datos?.detail) return String(datos.detail);
  if (status === 403) return "No tienes permiso para realizar esta acción.";
  if (status === 404) return "El registro solicitado no existe.";
  if (status >= 500) return "Error interno del servidor. Inténtalo de nuevo en unos segundos.";
  return `La API respondió con estado ${status}.`;
}

let renovacionEnCurso = null;
function renovarToken(refresh) {
  // Si varias peticiones vencen a la vez, todas esperan la misma renovación.
  renovacionEnCurso ??= fetch(construirUrl("auth/refresh/"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh }),
  })
    .then(async (respuesta) => {
      if (!respuesta.ok) return false;
      const datos = await respuesta.json();
      actualizarSesion({ access: datos.access });
      return true;
    })
    .catch(() => false)
    .finally(() => {
      renovacionEnCurso = null;
    });
  return renovacionEnCurso;
}

export async function apiRequest(ruta, { method = "GET", body, query, auth = true, reintentar = true } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const sesion = leerSesion();
  if (auth && sesion?.access) headers.Authorization = `Bearer ${sesion.access}`;

  let respuesta;
  try {
    respuesta = await fetch(construirUrl(ruta, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servidor. Verifica que la API esté encendida.");
  }

  if (respuesta.status === 401 && auth) {
    if (reintentar && sesion?.refresh && (await renovarToken(sesion.refresh))) {
      return apiRequest(ruta, { method, body, query, auth, reintentar: false });
    }
    borrarSesion();
    alExpirarSesion();
    throw new ApiError("Tu sesión expiró. Inicia sesión de nuevo.", { status: 401 });
  }

  if (respuesta.status === 204) return null;

  let datos = null;
  const texto = await respuesta.text();
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      throw new ApiError(`El servidor devolvió una respuesta inválida (HTTP ${respuesta.status}).`, {
        status: respuesta.status,
      });
    }
  }

  if (!respuesta.ok) {
    throw new ApiError(mensajeDeError(datos, respuesta.status), {
      status: respuesta.status,
      codigo: datos?.codigo ?? null,
      errores: datos?.errores ?? null,
    });
  }
  return datos;
}

// Atajos por verbo HTTP.
export const api = {
  get: (ruta, query) => apiRequest(ruta, { query }),
  post: (ruta, body = {}) => apiRequest(ruta, { method: "POST", body }),
  put: (ruta, body) => apiRequest(ruta, { method: "PUT", body }),
  patch: (ruta, body) => apiRequest(ruta, { method: "PATCH", body }),
  del: (ruta) => apiRequest(ruta, { method: "DELETE" }),
  login: (username, password) =>
    apiRequest("auth/login/", { method: "POST", body: { username, password }, auth: false }),
};
