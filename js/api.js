// Único punto de acceso al servicio Google Apps Script.
// Pega aquí la URL de implementación terminada en /exec.
export const API_URL = "https://script.google.com/macros/s/AKfycbwFFo3v-99dlZnnX1DCnKQRptBvtIH7ALxcNujmk8GLu31rVTz4EeeUaCYfvY0G6e0/exec";

export async function solicitar(resource, { method = "GET", action, data } = {}) {
  if (!API_URL.startsWith("https://script.google.com/macros/s/")) {
    throw new Error("Configura la URL del servicio en js/api.js antes de usar la aplicación.");
  }
  const url = `${API_URL}?resource=${encodeURIComponent(resource)}`;
  const opciones = { method, redirect: "follow" };
  if (method === "POST") {
    opciones.headers = { "Content-Type": "text/plain;charset=utf-8" };
    opciones.body = JSON.stringify({ action, data });
  }
  const respuesta = await fetch(url, opciones);
  if (!respuesta.ok) throw new Error(`El servicio respondió con estado ${respuesta.status}.`);
  const resultado = await respuesta.json();
  if (!resultado.success) throw new Error(resultado.message || "El servicio rechazó la operación.");
  return resultado.data;
}

export const listar = resource => solicitar(resource);
export const crear = (resource, data) => solicitar(resource, { method: "POST", action: "create", data });
export const actualizar = (resource, data) => solicitar(resource, { method: "POST", action: "update", data });
export const eliminar = (resource, data) => solicitar(resource, { method: "POST", action: "delete", data });

