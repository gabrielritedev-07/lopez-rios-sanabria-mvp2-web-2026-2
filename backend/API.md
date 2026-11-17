# Contrato de la API REST — POS Papel y Luna (MVP 3)

Base local: `http://127.0.0.1:8000/api/`. Todas las peticiones y respuestas usan JSON.
Todas las rutas terminan en `/`.

## Autenticación

Salvo `/api/salud/` y `/api/auth/login/` y `/api/auth/refresh/`, todo endpoint exige el encabezado:

```
Authorization: Bearer <access>
```

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| POST | `/api/auth/login/` | `{"username", "password"}` | `{"access", "refresh", "usuario": {"id", "username", "nombre", "rol"}}` |
| POST | `/api/auth/refresh/` | `{"refresh"}` | `{"access"}` |
| GET | `/api/auth/me/` | — | `{"id", "username", "nombre", "rol"}` |
| GET | `/api/salud/` | — | `{"estado": "ok"}` (público) |

- `rol` es `ADMINISTRADOR` o `CAJERO`.
- El access token dura 30 min y el refresh 8 h (configurable en `.env`).
- Cerrar sesión = el frontend borra los tokens de `sessionStorage`.
- Token vencido o inválido → `401` con `"codigo": "token_not_valid"`: el frontend intenta
  `/auth/refresh/` una vez y, si falla, vuelve al login.

## Formato de errores (todas las rutas)

```json
{
  "detail": "precio: El precio no puede ser negativo.",
  "codigo": "registros_asociados",
  "errores": { "precio": ["El precio no puede ser negativo."] }
}
```

`detail` siempre existe y se puede mostrar tal cual. `codigo` y `errores` son opcionales.

| Código HTTP | Significado |
|---|---|
| 400 | Datos inválidos (ver `errores` por campo) |
| 401 | Sin token, token inválido o vencido |
| 403 | El rol del usuario no permite la acción |
| 404 | El registro no existe |
| 409 | No se puede eliminar porque tiene registros asociados (`codigo: registros_asociados`) |

## Catálogo

Todos los listados aceptan búsqueda con `?q=texto`. Las listas se devuelven como arreglo JSON.

| Recurso | Rutas | Consultar | Crear / editar / eliminar |
|---|---|---|---|
| Categorías | `/api/categorias/`, `/api/categorias/{id}/` | Admin y cajero | Solo admin |
| Productos | `/api/productos/`, `/api/productos/{id}/` | Admin y cajero | Solo admin |
| Proveedores | `/api/proveedores/`, `/api/proveedores/{id}/` | Admin y cajero* | Solo admin |
| Descuentos | `/api/descuentos/`, `/api/descuentos/{id}/` | Admin y cajero** | Solo admin |
| Clientes | `/api/clientes/`, `/api/clientes/{id}/` | Admin y cajero | Admin y cajero |

\* El cajero solo consulta proveedores para elegir uno al registrar un faltante.
\** El cajero consulta descuentos para aplicar uno existente a la venta.

Métodos por ruta: `GET` lista, `POST` crea (201), `GET {id}` detalle, `PUT {id}` reemplaza,
`PATCH {id}` modifica parcialmente, `DELETE {id}` elimina (204, o 409 si tiene registros asociados).

### Producto

```json
{
  "id": 1,
  "codigo": "CU-100",
  "nombre": "Cuaderno rayado",
  "categoriaId": 2,
  "categoriaNombre": "Cuadernos",
  "precio": 5000,
  "costo": 3000,
  "seguimientoInventario": true,
  "stock": 10
}
```

- Obligatorios al crear: `nombre`, `categoriaId`, `precio`.
- `codigo` es opcional; si se envía, no se puede repetir (sin distinguir mayúsculas).
- `precio`, `costo` y `stock` son enteros en pesos/unidades, nunca negativos.
- Filtro adicional: `GET /api/productos/?categoria={id}`.

**Edición en caliente desde la venta (admin y cajero):**
`PATCH /api/productos/{id}/edicion-rapida/` acepta solo `nombre`, `codigo`, `categoriaId` y `precio`.
Cualquier otro campo (stock, costo, seguimientoInventario) se ignora. Devuelve el producto completo.

### Categoría

`{"id", "nombre"}` — nombre obligatorio y único sin distinguir mayúsculas.

### Cliente / Proveedor

`{"id", "nombre", "telefono", "correo"}` — solo `nombre` es obligatorio. El teléfono acepta números,
espacios, `+`, `-` y paréntesis.

### Descuento

```json
{ "id": 1, "nombre": "Estudiantes", "tipo": "PORCENTAJE", "tipoNombre": "Porcentaje", "valor": 10 }
```

- `tipo`: `PORCENTAJE` (valor de 1 a 100) o `VALOR_FIJO` (valor en pesos, mayor que 0).
- Eliminar un descuento no modifica las ventas que ya lo usaron (guardan una copia).

## Reglas de dinero

- Montos en pesos enteros. **Los precios de los productos ya incluyen IVA.**
- `subtotal` = suma de precio unitario × cantidad (precios tomados de la base de datos).
- `descuentoMonto` = porcentaje del subtotal (redondeado) o valor fijo. No puede superar el subtotal.
- `total` = `subtotal` − `descuentoMonto`.
- `ivaIncluido` = `total` − `total` / 1,19 (informativo para la factura; no se suma).
- El backend **ignora** cualquier precio, subtotal, total o cambio enviado por el frontend.

## Ventas

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/api/ventas/` | Admin y cajero | Historial. Filtros: `?estado=abierta\|cerrada`, `?desde=AAAA-MM-DD`, `?hasta=AAAA-MM-DD`, `?q=nombre cliente` |
| GET | `/api/ventas/{id}/` | Admin y cajero | Detalle / factura |
| POST | `/api/ventas/` | Admin y cajero | Crea venta abierta; con `"cerrar": true` la crea y la cierra en un paso |
| PUT/PATCH | `/api/ventas/{id}/` | Admin y cajero | Modifica una venta **abierta** |
| POST | `/api/ventas/{id}/cerrar/` | Admin y cajero | Cierra una venta abierta (puede enviar cambios de último momento) |
| POST | `/api/ventas/{id}/corregir/` | Solo admin | Corrige una venta **cerrada** |
| POST | `/api/ventas/{id}/reembolsos/` | Solo admin | Registra un reembolso parcial o total |

No existe DELETE: eliminar o anular ventas está fuera del alcance.

### Cuerpo para crear / editar / cerrar / corregir

```json
{
  "items": [ { "productoId": 3, "cantidad": 2 } ],
  "clienteId": 5,
  "metodoPago": "Efectivo",
  "descuentoId": 1,
  "valorRecibido": 50000,
  "cerrar": false
}
```

- Todos los campos son opcionales al editar; al crear, `items` es obligatorio (mínimo 1).
- Si el mismo `productoId` llega dos veces, las cantidades se suman.
- `metodoPago`: `Efectivo`, `Nequi` o `Debe`.
- `clienteId: null` quita el cliente; `descuentoId: null` quita el descuento.

**Al cerrar** se valida, en una sola transacción:
- al menos un producto;
- stock suficiente de los productos con inventario (si falta, el error nombra cada producto);
- `Debe` exige cliente;
- `Efectivo` exige `valorRecibido` ≥ `total` (se calcula `cambio`).

Luego se descuenta el stock. La venta toma los precios actuales de los productos, así que una
edición en caliente hecha antes de cerrar se refleja automáticamente.

### Corrección (solo admin)

Mismo cuerpo que arriba (sin `cerrar`). Reglas:
- Solo ventas cerradas y **sin reembolsos**.
- Conserva el `id`; marca `corregida: true`, `corregidaPor` y `corregidaEn`.
- Los productos que ya estaban conservan su precio original; los nuevos toman el precio actual.
- El stock se ajusta solo por la **diferencia** (si se venden 3 unidades más, salen 3; si se quita
  un producto, vuelve al stock). Si la corrección deja stock negativo, se rechaza nombrando el producto.
- Si no se envía `descuentoId`, se conserva el descuento original aunque ya no exista en el catálogo.

### Reembolso (solo admin)

```json
{
  "motivo": "Producto defectuoso",
  "items": [ { "productoId": 3, "cantidad": 1, "retornaInventario": true } ]
}
```

O reembolso total de lo que falte: `{ "todo": true, "retornaInventario": false }`.

- Solo ventas cerradas; nunca más unidades de las vendidas menos las ya reembolsadas.
- El valor se calcula proporcional al total pagado (respeta el descuento). Reembolsar todo devuelve
  exactamente el `total` de la venta.
- Solo suma stock si `retornaInventario` es `true` (por defecto `true`).
- La venta pasa a `estadoReembolso: "parcial"` o `"total"`. Cada reembolso guarda usuario y fecha.

### Respuesta de una venta

```json
{
  "id": 12, "numero": "V-012", "estado": "cerrada", "fecha": "2026-11-16T18:30:00-05:00",
  "clienteId": 5, "clienteNombre": "Ana", "metodoPago": "Efectivo",
  "subtotal": 22000, "descuentoId": 1,
  "descuento": { "nombre": "Diez", "tipo": "PORCENTAJE", "valor": 10, "monto": 2200 },
  "descuentoMonto": 2200, "total": 19800, "ivaPorcentaje": 19, "ivaIncluido": 3161,
  "valorRecibido": 20000, "cambio": 200,
  "creadaPor": "cajero", "cerradaPor": "cajero", "cerradaEn": "2026-11-16T18:30:00-05:00",
  "corregida": false, "corregidaPor": null, "corregidaEn": null,
  "estadoReembolso": "ninguno", "totalReembolsado": 0,
  "items": [
    { "id": 30, "productoId": 3, "nombre": "Cuaderno", "precioUnitario": 10000,
      "costoUnitario": 6000, "cantidad": 2, "subtotal": 20000, "cantidadReembolsada": 0 }
  ],
  "reembolsos": [
    { "id": 1, "fecha": "...", "usuario": "admin", "total": 9000, "motivo": "",
      "items": [ { "id": 1, "productoId": 3, "nombre": "Cuaderno", "cantidad": 1,
                   "valor": 9000, "retornaInventario": true } ] }
  ]
}
```

## Compras (solo admin)

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/compras/` | Lista. Filtros: `?desde=`, `?hasta=`, `?proveedor={id}` |
| GET | `/api/compras/{id}/` | Detalle |
| POST | `/api/compras/` | Registra la compra |

```json
{
  "proveedorId": 2,
  "fecha": "2026-11-16",
  "items": [ { "productoId": 3, "cantidad": 10, "costo": 6500 } ]
}
```

- `fecha` es opcional (por defecto hoy) y no puede ser futura.
- Cada producto una sola vez; cantidad ≥ 1; costo ≥ 0.
- En una sola transacción: guarda la compra, actualiza el `costo` del producto con el último
  costo de compra y suma stock a los productos con seguimiento de inventario.

Respuesta: `{"id", "numero": "CO-001", "fecha", "proveedorId", "proveedorNombre", "total",
"registradaPor", "items": [{"id", "productoId", "nombre", "costoUnitario", "cantidad", "subtotal"}]}`.

## Faltantes (demanda no atendida)

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/api/faltantes/` | Admin y cajero | Lista. Filtros: `?tipo=inexistente\|agotado`, `?proveedor={id}\|ninguno`, `?estado=pendiente\|resuelto`, `?desde=`, `?hasta=`, `?q=texto` |
| POST | `/api/faltantes/` | Admin y cajero | Registra un faltante |
| GET | `/api/faltantes/{id}/` | Admin y cajero | Detalle |
| POST | `/api/faltantes/{id}/resolver/` | Solo admin | Marca como resuelto (guarda quién y cuándo) |
| DELETE | `/api/faltantes/{id}/` | Solo admin | Elimina un registro equivocado |
| GET | `/api/faltantes/pendientes/` | Solo admin | Pendientes agrupados por producto y proveedor (para planear compras). Acepta los mismos filtros |

```json
{ "nombre": "Lápices de colores", "cantidad": 3, "tipo": "inexistente", "proveedorId": 2 }
{ "productoId": 7, "cantidad": 2, "tipo": "agotado" }
```

- `tipo: "agotado"` exige `productoId` (producto del catálogo).
- `tipo: "inexistente"` exige `nombre` y no admite `productoId`.
- `proveedorId` es opcional. `cantidad` por defecto es 1.
- Se guarda `nombre` (como lo pidió el cliente) y `nombreNormalizado`: minúsculas, sin tildes,
  espacios simples y plural simple por palabra (`ces`→`z`, `es` tras consonante, `s` final; no
  se tocan palabras de menos de 5 letras ni las que terminan en vocal tildada + s).
  Ej.: "Lápices  de Colores" → "lapiz de color".

Cada grupo de `/pendientes/` trae: `productoId`, `nombre`, `nombreNormalizado`, `proveedorId`,
`proveedorNombre`, `solicitudes`, `cantidadTotal`, `pendientes`, `tipos`, `primeraSolicitud`,
`ultimaSolicitud`, `stockActual` y `ids` (para resolver el grupo completo).

## Reportes (solo admin)

Todos aceptan `?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` (ambos días incluidos; un día = mismas fechas).
Si no se envían fechas, el rango es **hoy**. Solo cuentan ventas **cerradas**, por su fecha de cierre.

| Ruta | Respuesta |
|---|---|
| `GET /api/reportes/ventas/` | `cantidadVentas`, `subtotal`, `descuentos`, `totalVendido`, `ivaIncluido`, `totalReembolsado` (reembolsos hechos en el rango), `totalNeto`, `ticketPromedio`, `porMetodoPago[]`, `porDia[]` |
| `GET /api/reportes/productos-mas-vendidos/?limite=10` | `productos[]`: `posicion`, `productoId`, `nombre`, `unidadesVendidas`, `unidadesReembolsadas`, `unidadesNetas`, `ingresos`, `ventas` |
| `GET /api/reportes/compras/` | `cantidadCompras`, `totalComprado`, `porProveedor[]`, `compras[]` |
| `GET /api/reportes/faltantes-frecuentes/?limite=10&estado=` | `faltantes[]` agrupados por producto, ordenados por número de solicitudes. Sin fechas = todo el historial |

`limite` va de 1 a 100.

---

## Funcionalidades comerciales (ampliación posterior al MVP 3)

### Costos visibles solo para el administrador

`costo` (productos) y `costoUnitario` (líneas de venta) **no aparecen** en las respuestas cuando
consulta un cajero. Márgenes, ganancias y reportes financieros son exclusivos del administrador.

### Productos: stock mínimo, vencimiento, alertas y kardex

Campos nuevos del producto:

| Campo | Tipo | Notas |
|---|---|---|
| `stockMinimo` | entero ≥ 0 | Por defecto 5. Con stock igual o menor el producto queda en "Stock bajo" |
| `fechaVencimiento` | `AAAA-MM-DD` o `null` | Opcional (útil en la dulcería) |
| `estadoStock` | solo lectura | `null` (sin inventario), `agotado`, `bajo` u `ok` |
| `alertaVencimiento` | solo lectura | `null`, `vencido`, `proximo` (≤ 15 días, `POS_DIAS_ALERTA_VENCIMIENTO`) u `ok` |
| `diasParaVencer` | solo lectura | días que faltan (negativo si ya venció) |

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/api/productos/alertas/` | Admin y cajero | `{agotados[], stockBajo[], porVencer[], vencidos[], diasAlertaVencimiento}` |
| GET | `/api/productos/{id}/kardex/` | Admin y cajero | `{producto, movimientos[]}` del más reciente al más antiguo |
| POST | `/api/productos/{id}/ajustar-stock/` | Solo admin | `{stock, motivo}`: fija el stock contado y lo registra como ajuste |

Movimiento del kardex: `{id, fecha, tipo, tipoNombre, cantidad, stockAnterior, stockResultante,
usuario, referencia, nota}`. `tipo`: `INICIAL`, `AJUSTE`, `COMPRA`, `VENTA`, `CORRECCION`,
`REEMBOLSO`. `cantidad` positiva = entra; negativa = sale. Se registra solo en productos con
inventario. Editar el stock desde el formulario del producto también genera un `AJUSTE`.

### Ventas: ítems libres / servicios rápidos

Además de `{productoId, cantidad}`, una línea puede ser `{descripcion, precio, cantidad}` (fotocopias,
anillados, minutos…). No mueve inventario y su costo es 0. En la respuesta la línea trae
`productoId: null` y `esLibre: true`.

Reembolsos: cada línea puede identificarse con `detalleId` (id de la línea, sirve para ítems libres)
o con `productoId`.

### Cartera de clientes ("Debe") y abonos

`saldo = ventas cerradas en Debe − reembolsos de esas ventas − abonos`. El listado de clientes trae
`saldo` en cada cliente.

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| GET | `/api/clientes/{id}/cartera/` | Admin y cajero | `{saldo, totalFiado, totalReembolsado, totalAbonado, ventas[], abonos[]}` |
| POST | `/api/clientes/{id}/abonos/` | Admin y cajero | `{valor, metodoPago: "Efectivo"\|"Nequi", nota}`; no puede superar el saldo |

Un cliente con ventas o abonos no se puede eliminar (409).

### Caja: turnos y arqueo

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/caja/turno-actual/` | `{abierto, turno}` con el resumen calculado en vivo |
| POST | `/api/caja/abrir/` | `{baseInicial}` (un turno abierto por usuario) |
| POST | `/api/caja/cerrar/` | `{efectivoContado, observaciones}` → guarda el arqueo |
| GET | `/api/caja/turnos/` | Historial: el cajero ve los suyos; el admin todos (`?usuario=`, `?desde=`, `?hasta=`) |

`efectivoEsperado = baseInicial + ventasEfectivo + abonosEfectivo − reembolsosEfectivo`, contando solo
lo que hizo el usuario del turno. `diferencia = efectivoContado − efectivoEsperado` y `resultado` es
`sobrante`, `faltante` o `cuadrado`. El turno también informa `ventasNequi`, `ventasDebe`,
`abonosNequi` y `cantidadVentas`.

### Tablero del administrador (solo admin)

| Ruta | Respuesta |
|---|---|
| `GET /api/reportes/resumen-dia/?fecha=` (hoy por defecto) | `totalVendido`, `cantidadVentas`, `ticketPromedio`, `descuentos`, `totalReembolsado`, `costoVendido`, `gananciaEstimada`, `porMetodoPago[]` (`total` y `abonos` de Efectivo, Nequi y Debe), `totalAbonos`, `dineroRecibido` |
| `GET /api/reportes/top-productos/?periodo=hoy\|semana\|mes&limite=5` | `porUnidades[]` y `porGanancia[]` con `unidades`, `ingresos`, `costo`, `ganancia`, `margen` (%) |
| `GET /api/reportes/tendencia/?dias=7\|30` | `dias[]` con `fecha`, `ingresos`, `costos`, `ganancia`, `ventas` (incluye días en cero) |
| `GET /api/compras/sugerencia-pedido/` | Lista de pedido agrupada por proveedor |

- `gananciaEstimada = (total vendido − reembolsos) − (costo de lo vendido − costo de lo reembolsado)`,
  con el costo guardado en cada línea al vender.
- `semana` empieza el lunes; `mes`, el día 1.
- Sugerencia de pedido: productos con stock en el mínimo o por debajo, más los faltantes pendientes.
  `sugerido = max(2 × stockMinimo − stock, 0) + unidades pedidas por clientes`. Para productos que no
  existen en el catálogo se sugiere la cantidad total pedida. El proveedor es el de la última compra
  del producto (o el que anotó el cajero en el faltante).
