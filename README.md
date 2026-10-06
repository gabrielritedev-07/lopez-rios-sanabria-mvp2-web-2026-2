# POS Papel y Luna MVP 2

Aplicación web de punto de venta en HTML, CSS y JavaScript vanilla. Los productos, ventas, compras, clientes, proveedores y categorías se leen y escriben en Google Sheets mediante una Web App de Google Apps Script. La aplicación no usa `localStorage` como fuente de datos.

## Configuración

1. Crea una hoja de cálculo con pestañas `productos`, `ventas`, `compras`, `clientes`, `proveedores` y `categorias`.
2. Añade a cada pestaña los encabezados que define la Guía Backend Google Sheets – POS MVP 2. Mantén sus nombres y orden exactos. Las relaciones usan ids (`categoriaId`, `clienteId`, `proveedorId`); ventas y compras guardan sus líneas en `itemsJson`.
3. Publica el script de Apps Script como aplicación web y copia su URL terminada en `/exec`.
4. Pega esa URL en `API_URL` en `js/api.js`.
5. Sirve esta carpeta por HTTPS o desde `localhost` (por ejemplo, la extensión Live Server de VS Code). No abras `index.html` como archivo local: el navegador bloquea módulos ES cuando se usa el protocolo `file://`.

El archivo `apps-script/Code.gs` contiene la implementación de GET y de las operaciones `create`, `update` y `delete`. Copia su contenido al editor de Apps Script, guarda y publica una nueva versión de la aplicación web con acceso para cualquier persona. La guía del curso explica cómo desplegarla.

El contrato esperado del servicio es `GET ?resource=productos` para listar y `POST ?resource=productos` con JSON `{ "action": "create|update|delete", "data": { ... } }` para mutaciones. Las respuestas deben seguir `{ "success": true, "data": ... }` o `{ "success": false, "message": "..." }`. Para POST se envía JSON como `text/plain` para evitar preflight de CORS. Revisa que el despliegue de Apps Script permita acceso desde el navegador.

## Campos usados por el frontend

- **productos:** `id`, `codigo`, `nombre`, `categoriaId`, `precio`, `costo`, `seguimientoInventario`, `stock`.
- **ventas:** `id`, `fecha`, `estado` (`abierta` o `cerrada`), `clienteId`, `metodoPago` (`Efectivo`, `Nequi` o `Debe`), `subtotal`, `total`, `valorRecibido`, `cambio`, `itemsJson`, `actualizadoEn`.
- **compras:** `id`, `fecha`, `proveedorId`, `total`, `itemsJson`.
- **categorias:** `id`, `nombre`.
- **proveedores / clientes:** `id`, `nombre`, `telefono`, `correo`.

Cada línea en `itemsJson` conserva `productoId`, `nombre`, `precio`, `costo` y `cantidad` como fotografía del momento de la operación. Los importes son números en pesos enteros y las fechas se almacenan en ISO 8601.

## Identificadores y cliente en la venta

Los registros nuevos reciben automáticamente un id legible, con prefijo y consecutivo: `PR-001` para productos, `P-001` para proveedores, `C-001` para clientes, `V-001` para ventas, `CAT-001` para categorías y `CO-001` para compras. El consecutivo se calcula a partir del mayor id existente de ese tipo; los ids anteriores no se cambian para conservar sus relaciones. El POS muestra el id de la venta actual y el formulario muestra el id sugerido antes de guardar.

En el carrito, el cliente es opcional para ventas de mostrador y obligatorio para pago `Debe`. El botón `+ Agregar cliente` permite crear un cliente sin salir de la venta; al guardarlo queda seleccionado automáticamente. También se refresca el selector si se crea un cliente desde el módulo Entidades. Cuando eliges uno existente se muestran su nombre y datos de contacto.

## Migración desde MVP 1

El navegador ya no toma datos de la persistencia del MVP 1. Carga las entidades desde las pestañas de Google Sheets. Migra manualmente cada producto y venta que se deba conservar; crea primero las categorías y relaciona cada producto con su `categoriaId`. Si un producto antiguo conserva el nombre de la categoría en una columna de texto, el formulario puede asociarlo por coincidencia exacta con una categoría ya cargada. No se crean registros ficticios ni semilla local.

## Módulos incluidos

- Catálogo buscable y filtrable, carrito, medios de pago heredados, efectivo y cambio. La app carga primero productos, categorías y clientes; historial, compras y proveedores se consultan al abrir esos módulos, con un indicador circular mientras hay peticiones.
- Ventas abiertas persistidas, edición, retoma y cierre con asociación opcional de cliente (requerido para `Debe`).
- Historial, detalle de factura e impresión/guardar como PDF.
- CRUD de productos y edición de producto directamente desde el catálogo de venta.
- Compras vinculadas a proveedores y productos; listado y actualización de stock/costo cuando el producto lleva inventario.
- CRUD de categorías, proveedores y clientes; se impide eliminar entidades con relaciones existentes.
- Validación de stock antes del cierre; los productos sin seguimiento no alteran stock.

## Nota de inventario

Apps Script ofrece operaciones por registro, no una transacción atómica para actualizar varias hojas. El frontend guarda la venta confirmada y luego actualiza los productos involucrados; mantén el servicio accesible durante el cierre y revisa el estado de las hojas si una petición de inventario falla a mitad de la operación. Para concurrencia real entre varios cajeros, este modelo requiere una capa transaccional, fuera del alcance de MVP 2.

## Ejecutar y publicar

**No abras `index.html` con doble clic.** Al usar `file://`, Chrome bloquea `type="module"` y los botones quedan sin funciones.

### Ejecutar localmente desde VS Code

1. Abre esta carpeta (`proyectoLibreria`) en VS Code.
2. Abre Terminal → Nueva terminal y ejecuta `py -m http.server 5500`.
3. En Chrome visita `http://localhost:5500`.
4. Para parar el servidor, vuelve a la terminal y pulsa `Ctrl+C`.

También puedes usar Live Server, pero abre la dirección `http://127.0.0.1:...` que muestra la extensión.

### Publicar con GitHub Pages

1. Crea un repositorio de GitHub y sube **el contenido de esta carpeta** a su raíz; `index.html` debe quedar en la raíz del repositorio.
2. En GitHub abre Settings → Pages.
3. En “Build and deployment”, elige “Deploy from a branch”, selecciona la rama donde subiste los archivos y la carpeta `/ (root)`, y pulsa Save.
4. Cuando GitHub Pages termine de publicar, abre `https://USUARIO.github.io/REPOSITORIO/`.
5. En `js/api.js`, configura la URL `/exec` de Apps Script antes de subir los archivos.

### Comprobar el backend

GitHub Pages solo hospeda el frontend; las lecturas y escrituras requieren que Apps Script responda. Abre `https://script.google.com/macros/s/ID_DEL_DESPLIEGUE/exec?resource=productos`: debe mostrar JSON con `success` y `data`. Si muestra “Script function not found: doGet”, pega `apps-script/Code.gs` completo en el proyecto de Apps Script asociado a la hoja, guarda y vuelve a implementar una **nueva versión** de la aplicación web. En “Nueva implementación → Aplicación web”, configura “Ejecutar como: Yo” y “Quién tiene acceso: Cualquier persona” (si la cuenta/organización lo permite), acepta los permisos del propietario y publica. Después verifica el endpoint otra vez. Si se crea una nueva versión, actualiza la implementación existente y vuelve a publicar; la URL `/exec` normalmente se conserva.

No se incluyen dependencias instaladas ni artefactos compilados.

