// Configuración del frontend.
// En desarrollo (localhost) usa el backend local de Django.
// Al desplegar, API_PRODUCCION apunta al backend publicado en Render.
const API_LOCAL = "http://127.0.0.1:8000/api/";
const API_PRODUCCION = "https://papel-luna-api.onrender.com/api/";

const esLocal = ["localhost", "127.0.0.1", ""].includes(location.hostname);

export const API_URL = esLocal ? API_LOCAL : API_PRODUCCION;

// Solo para la vista previa del carrito. El backend es quien calcula los valores reales.
// Los precios ya incluyen IVA: este porcentaje solo sirve para mostrar el IVA contenido.
export const IVA_PORCENTAJE = 19;
