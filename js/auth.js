// Inicio y cierre de sesión.
import { api } from "./api.js";
import { actualizarSesion, borrarSesion, guardarSesion, leerSesion } from "./sesion.js";

export async function iniciarSesion(username, password) {
  const datos = await api.login(username, password);
  guardarSesion({ access: datos.access, refresh: datos.refresh, usuario: datos.usuario });
  return datos.usuario;
}

// Al recargar la página: si hay tokens guardados, confirma con el backend que siguen válidos.
export async function recuperarSesion() {
  if (!leerSesion()?.access) return null;
  try {
    const usuario = await api.get("auth/me/");
    actualizarSesion({ usuario });
    return usuario;
  } catch {
    borrarSesion();
    return null;
  }
}

export function cerrarSesion() {
  borrarSesion();
}
