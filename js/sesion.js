// Guarda la sesión (tokens JWT y datos del usuario) en sessionStorage.
// sessionStorage se borra al cerrar la pestaña. NO se guardan datos del negocio:
// productos, ventas, etc. viven solo en la base de datos y se piden a la API.
const CLAVE = "pos-papel-luna-sesion";

export function leerSesion() {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE));
  } catch {
    return null;
  }
}

export function guardarSesion(sesion) {
  sessionStorage.setItem(CLAVE, JSON.stringify(sesion));
}

export function actualizarSesion(cambios) {
  const actual = leerSesion();
  if (actual) guardarSesion({ ...actual, ...cambios });
}

export function borrarSesion() {
  sessionStorage.removeItem(CLAVE);
}

export const usuarioActual = () => leerSesion()?.usuario ?? null;

// El rol solo decide qué se MUESTRA. El backend vuelve a validar el permiso en cada petición.
export const esAdmin = () => usuarioActual()?.rol === "ADMINISTRADOR";
