// Punto de entrada del frontend.
// 1. Si hay sesión válida, entra a la aplicación; si no, muestra el login.
// 2. Muestra u oculta opciones según el rol (el backend vuelve a validar cada permiso).
// 3. Registra las pantallas y la navegación.
import { alCerrarSesionPorVencimiento } from "./api.js";
import { cerrarSesion, iniciarSesion, recuperarSesion } from "./auth.js";
import { cargar, estado, limpiarEstado } from "./estado.js";
import { irA, registrarPagina } from "./navegacion.js";
import { esAdmin } from "./sesion.js";
import { $, $$, avisar, cerrarFormulario, iniciarFormularios, intentar } from "./ui.js";
import * as compras from "./modulos/compras.js";
import * as descuentos from "./modulos/descuentos.js";
import * as entidades from "./modulos/entidades.js";
import * as faltantes from "./modulos/faltantes.js";
import * as historial from "./modulos/historial.js";
import * as productos from "./modulos/productos.js";
import * as reportes from "./modulos/reportes.js";
import * as venta from "./modulos/venta.js";

const PAGINAS = { venta, ventas: historial, productos, compras, entidades, descuentos, faltantes, reportes, comprobante: {} };

function iniciarModulos() {
  iniciarFormularios();
  for (const [nombre, modulo] of Object.entries(PAGINAS)) {
    registrarPagina(nombre, modulo);
    modulo.iniciar?.();
  }
  entidades.suscribirClientes(venta.refrescarSelectores);
  descuentos.suscribirDescuentos(venta.refrescarSelectores);

  document.addEventListener("click", (e) => {
    const destino = e.target.closest("[data-page]");
    if (destino) irA(destino.dataset.page);
  });
  $(".brand").addEventListener("click", (e) => {
    e.preventDefault();
    irA("venta");
  });
  $("#login-form").addEventListener("submit", entrarConFormulario);
  $("#logout").addEventListener("click", salir);
}

function mostrarLogin(mensaje = "", esError = true) {
  cerrarFormulario();
  limpiarEstado();
  $("#app").hidden = true;
  $("#login-screen").hidden = false;
  const aviso = $("#login-error");
  aviso.textContent = mensaje;
  aviso.className = esError ? "form-error" : "input-note is-ok";
  $("#login-password").value = "";
  $("#login-user").focus();
}

async function entrarALaApp(usuario) {
  $("#login-screen").hidden = true;
  $("#app").hidden = false;
  $("#user-name").textContent = usuario.nombre;
  $("#user-role").textContent = usuario.rol === "ADMINISTRADOR" ? "Administrador" : "Cajero";
  document.body.dataset.rol = usuario.rol;
  // Control visual por rol: oculta lo que el usuario no puede usar.
  $$("[data-solo-admin]").forEach((elemento) => {
    elemento.hidden = !esAdmin();
  });
  await intentar(() => cargar("categorias", "clientes", "proveedores", "descuentos"), {
    cargando: "Cargando datos del negocio…",
  });
  await irA("venta");
  avisar(`Hola, ${usuario.nombre}. Sesión iniciada como ${$("#user-role").textContent.toLowerCase()}.`);
}

async function entrarConFormulario(evento) {
  evento.preventDefault();
  const usuario = $("#login-user").value.trim();
  const clave = $("#login-password").value;
  const aviso = $("#login-error");
  if (!usuario || !clave) {
    aviso.className = "form-error";
    aviso.textContent = "Escribe tu usuario y tu contraseña.";
    return;
  }
  const boton = $("#login-submit");
  boton.disabled = true;
  boton.textContent = "Ingresando…";
  aviso.textContent = "";
  // El servidor gratuito se "duerme" tras 15 min sin uso y tarda cerca de un minuto en despertar.
  const avisoLento = setTimeout(() => {
    aviso.className = "input-note";
    aviso.textContent = "El servidor se está activando; la primera conexión puede tardar hasta un minuto…";
  }, 5000);
  try {
    const datos = await iniciarSesion(usuario, clave);
    await entrarALaApp(datos);
  } catch (error) {
    aviso.className = "form-error";
    aviso.textContent = error.message;
  } finally {
    clearTimeout(avisoLento);
    if (aviso.textContent.startsWith("El servidor se está activando")) aviso.textContent = "";
    boton.disabled = false;
    boton.textContent = "Ingresar";
  }
}

function salir() {
  const ventaSinGuardar = estado.venta && estado.venta.items.length && !estado.venta.id;
  if (ventaSinGuardar && !window.confirm("Hay una venta sin guardar. ¿Cerrar sesión de todas formas?")) return;
  cerrarSesion();
  mostrarLogin("Cerraste sesión correctamente.", false);
}

async function arrancar() {
  iniciarModulos();
  alCerrarSesionPorVencimiento(() => mostrarLogin("Tu sesión expiró. Inicia sesión de nuevo."));
  const usuario = await recuperarSesion();
  if (usuario) await entrarALaApp(usuario);
  else mostrarLogin();
}

arrancar();
