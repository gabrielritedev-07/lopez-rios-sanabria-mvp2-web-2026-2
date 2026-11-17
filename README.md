# POS Papel y Luna — MVP 3 (Entrega final)

Sistema de punto de venta para la papelería **Papel y Luna**. Desarrollo de Aplicaciones Web, 2026-2.

| | URL |
|---|---|
| **Frontend** | https://claudiosgproyectos-max.github.io/lopez-rios-sanabria-mvp2-web-2026-2/ |
| **API (backend)** | `https://NOMBRE-SERVICIO.onrender.com/api/` ← *reemplazar tras crear el servicio en Render* |
| Comprobación de la API | `https://NOMBRE-SERVICIO.onrender.com/api/salud/` |
| Repositorio | https://github.com/claudiosgproyectos-max/lopez-rios-sanabria-mvp2-web-2026-2 |

> El backend usa el plan gratuito de Render: tras 15 minutos sin uso se suspende y la primera
> petición tarda cerca de un minuto en responder. Después funciona con normalidad.

## Credenciales de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `Admin.PyL2026` |
| Cajero | `cajero` | `Cajero.PyL2026` |

Se crean con `python manage.py crear_usuarios_iniciales` (ver más abajo). Se pueden cambiar con las
variables `POS_ADMIN_*` y `POS_CAJERO_*` del archivo `.env`.

## Integrantes

- [Nombre completo] López
- [Nombre completo] Ríos
- [Nombre completo] Sanabria

---

## 1. Arquitectura

```text
Frontend (HTML + CSS + JavaScript Vanilla, módulos ES)      → GitHub Pages
        │  fetch() con JSON y encabezado Authorization: Bearer <JWT>
        ▼
API REST: Django 6.1 + Django REST Framework + SimpleJWT     → Render
        │  ORM de Django, transacciones atómicas
        ▼
PostgreSQL                                                   → Neon
```

- El frontend **no guarda datos del negocio**: todo se lee y se escribe en la API. En `sessionStorage`
  solo viven los tokens de la sesión.
- El backend es la **fuente confiable de cálculos**: precios, subtotales, descuentos, totales, cambio,
  reembolsos y stock se calculan en el servidor. Lo que envíe el frontend se valida y se recalcula.
- Las operaciones que tocan ventas e inventario a la vez (cerrar venta, corregir, reembolsar,
  registrar compra) corren en `transaction.atomic()` con `select_for_update()`: si algo falla, no
  quedan datos a medias y dos cajeros no pueden descontar el mismo stock al mismo tiempo.

### Estructura del proyecto

```text
├── index.html              # Única página: login + aplicación
├── style.css               # Estilos (identidad visual de Papel y Luna, responsive)
├── assets/                 # Logo e íconos
├── js/
│   ├── app.js              # Arranque, login/logout, menú por rol
│   ├── api.js              # apiClient: fetch, JWT, renovación de token, errores
│   ├── auth.js / sesion.js # Inicio de sesión y almacenamiento de tokens
│   ├── config.js           # URL de la API (local / producción)
│   ├── estado.js           # Copia en memoria de los catálogos
│   ├── navegacion.js       # Cambio de pantallas
│   ├── ui.js               # Formato, mensajes y formularios en diálogo
│   └── modulos/            # Una pantalla por archivo: venta, historial, productos,
│                           # compras, entidades, descuentos, faltantes, reportes
├── backend/
│   ├── config/             # settings, urls, manejo de errores, filtros de fecha
│   ├── apps/
│   │   ├── usuarios/       # Perfil y rol, login JWT, permisos, comandos de datos iniciales
│   │   ├── catalogo/       # Productos, categorías, clientes, proveedores, descuentos, inventario
│   │   ├── ventas/         # Ventas, detalles, corrección, reembolsos (services.py)
│   │   ├── compras/        # Compras y detalles (services.py)
│   │   ├── faltantes/      # Demanda no atendida y normalización de nombres
│   │   └── reportes/       # Consultas agregadas
│   ├── API.md              # Contrato completo de la API
│   ├── requirements.txt
│   ├── build.sh            # Build en Render
│   └── .env.example        # Variables de entorno (copiar a .env)
└── crear-zip.ps1           # Genera el ZIP de entrega
```

Cada app separa `models.py` (entidades), `serializers.py` (validación y JSON), `views.py`
(coordinación HTTP), `urls.py` (rutas), `services.py` (reglas de negocio con transacciones)
y `tests.py`. Los permisos por rol están en `apps/usuarios/permissions.py`.

## 2. Funcionalidades

**Heredadas (MVP 1 y 2), ahora sobre el backend propio:** venta con método de pago (Efectivo, Nequi,
Debe), valor recibido y cambio; factura imprimible o en PDF; historial; ventas abiertas (guardar,
retomar y cerrar); edición de un producto desde la venta; CRUD de productos, categorías, proveedores y
clientes; compras con detalle; inventario (no se cierra una venta que deje stock negativo); cliente
obligatorio para pago Debe; no se eliminan registros con datos asociados.

**Nuevas (MVP 3):**

- **Autenticación JWT** con roles administrador y cajero, sesión persistente durante la pestaña,
  renovación automática del token y cierre de sesión.
- **Descuentos**: catálogo (porcentaje o valor fijo), uno por venta, sobre el total, sin totales negativos.
- **Corrección de ventas cerradas**: conserva el número de venta, registra quién y cuándo, y ajusta el
  inventario solo por la diferencia.
- **Reembolsos** parciales o totales, proporcionales al descuento, con opción de devolver al inventario.
- **Faltantes**: productos inexistentes o agotados, con filtros, resolución y vista agrupada para compras.
- **Reportes**: ventas totales, productos más vendidos, compras y faltantes frecuentes por rango de fechas.

### Permisos por rol

| Función | Administrador | Cajero |
|---|:---:|:---:|
| Ventas: crear, guardar, retomar y cerrar; historial y factura | ✔ | ✔ |
| Aplicar un descuento existente | ✔ | ✔ |
| Registrar y consultar faltantes | ✔ | ✔ |
| Gestionar clientes | ✔ | ✔ |
| Consultar productos, categorías y proveedores | ✔ | ✔ |
| Editar un producto desde la venta (nombre, código, categoría, precio) | ✔ | ✔ |
| Crear, editar y eliminar productos, categorías y proveedores | ✔ | — |
| Compras | ✔ | — |
| Catálogo de descuentos | ✔ | — |
| Corregir ventas y reembolsar | ✔ | — |
| Resolver faltantes y vista para compras | ✔ | — |
| Reportes | ✔ | — |

Se aplican en dos niveles: el frontend oculta lo que el rol no puede usar y el backend rechaza con
`403` cualquier petición no autorizada, aunque se llame la URL directamente.

### Reglas de negocio y decisiones

- **Los precios ya incluyen IVA.** `total = subtotal − descuento`. La factura informa el IVA contenido
  en el total (19 %: `total − total / 1,19`); no se suma.
- Cada línea de venta y compra guarda una copia del nombre, precio y costo del producto al momento de la
  operación, así el historial no cambia si luego se edita el producto.
- La venta guarda una copia del descuento aplicado: eliminar el descuento del catálogo no altera ventas pasadas.
- Una venta abierta toma los precios actuales al guardarse o cerrarse (por eso la edición en caliente se
  refleja en la venta en curso).
- En una corrección, los productos que ya estaban conservan su precio original; los nuevos toman el actual.
- Una venta con reembolsos ya no se puede corregir (primero se corrige, después se reembolsa).
- Reembolsar todas las unidades devuelve exactamente el total pagado (el valor se reparte entre las líneas sin
  errores de redondeo).
- Cada compra actualiza el costo del producto con el último costo y suma stock a los productos con inventario.
- Faltantes en texto se agrupan por nombre normalizado: minúsculas, sin tildes, espacios simples y plural
  simple por palabra (`ces`→`z`, `es` tras consonante, `s` final; no se tocan palabras de menos de 5 letras
  ni las terminadas en vocal tildada + s). Ej.: “Lápices de Colores” → “lapiz de color”.

La API completa (rutas, cuerpos JSON, respuestas y códigos de error) está en
[`backend/API.md`](backend/API.md).

## 3. Instalación local (Windows)

Requisitos: Python 3.12 o superior, PostgreSQL y Git.

### 3.1 Base de datos

Instala PostgreSQL y crea la base de datos (desde **SQL Shell (psql)**):

```sql
CREATE DATABASE pos_papel_luna;
```

### 3.2 Backend

```powershell
cd backend
py -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env        # ajusta DATABASE_URL con tu usuario y contraseña de PostgreSQL
python manage.py migrate
python manage.py crear_usuarios_iniciales
python manage.py cargar_datos_demo      # opcional: catálogo de ejemplo
python manage.py runserver
```

La API queda en `http://127.0.0.1:8000/api/` y el panel de Django en `http://127.0.0.1:8000/admin/`.

### 3.3 Frontend

En otra terminal, desde la raíz del proyecto:

```powershell
py -m http.server 5500
```

Abre `http://localhost:5500`. No abras `index.html` con doble clic: el navegador bloquea los módulos
JavaScript con `file://`.

### 3.4 Variables de entorno (`backend/.env`)

| Variable | Descripción |
|---|---|
| `DJANGO_DEBUG` | `True` en desarrollo, `False` en producción |
| `DJANGO_SECRET_KEY` | Clave secreta (obligatoria en producción) |
| `DJANGO_ALLOWED_HOSTS` | Dominios permitidos, separados por coma (Render se agrega solo) |
| `DATABASE_URL` | `postgresql://usuario:clave@host:5432/base` |
| `DB_SSL_REQUIRE` | `True` para bases en la nube (Neon) |
| `CORS_ALLOWED_ORIGINS` | Orígenes del frontend, sin `/` final |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_HOURS` | Duración de los tokens (30 min / 8 h) |
| `POS_IVA_PORCENTAJE` | IVA incluido en los precios (19) |
| `POS_ADMIN_*`, `POS_CAJERO_*` | Usuarios iniciales |
| `POS_CARGAR_DEMO` | `True` para cargar el catálogo de ejemplo en el build de Render |

El archivo `.env` nunca se sube a Git.

### 3.5 Scripts de base de datos e inicialización

- **Esquema:** lo crean las migraciones de Django (`backend/apps/*/migrations/`) con `python manage.py migrate`.
  El script `crear-zip.ps1` exporta el SQL equivalente a `backend/sql/esquema.sql`.
- **Usuarios iniciales:** `python manage.py crear_usuarios_iniciales` (idempotente).
- **Datos de ejemplo:** `python manage.py cargar_datos_demo` (idempotente).

## 4. Pruebas

### Automáticas (82 pruebas del backend)

```powershell
cd backend
.\env\Scripts\Activate.ps1
python manage.py test
```

Cubren autenticación, permisos por rol (incluido el acceso directo a endpoints de administrador),
validaciones, protección de registros asociados, cálculo de totales con IVA incluido y descuentos,
cierre de ventas, stock insuficiente, corrección con ajuste diferencial de inventario, reembolsos
proporcionales, compras, faltantes, reportes y la consistencia ante un fallo a mitad de una transacción.

### Manuales (lista de verificación)

- [ ] Login incorrecto muestra error; login correcto entra con el rol indicado.
- [ ] Al recargar la página la sesión se mantiene; “Cerrar sesión” vuelve al login.
- [ ] Cajero: no ve Compras, Descuentos ni Reportes; no puede crear productos.
- [ ] Venta en efectivo con cambio; venta Debe exige cliente; venta con descuento.
- [ ] Guardar venta abierta, retomarla desde Ventas y cerrarla.
- [ ] Intentar vender más unidades que el stock: se bloquea indicando el producto.
- [ ] Factura: imprimir o guardar como PDF.
- [ ] Admin: registrar compra y ver el stock actualizado.
- [ ] Admin: corregir una venta (cambiar cantidades) y ver la marca “Corregida” en historial y factura.
- [ ] Admin: reembolso parcial con y sin retorno al inventario; luego reembolso total.
- [ ] Eliminar una categoría con productos: muestra que tiene registros asociados.
- [ ] Registrar faltantes desde el punto de venta y verlos agrupados en “Para próximas compras”.
- [ ] Reportes de hoy y de los últimos 7 días.
- [ ] Recargar la página tras cada operación: los datos siguen ahí (persistencia en PostgreSQL).
- [ ] Probar en el celular (menú horizontal, carrito debajo del catálogo).

## 5. Despliegue

Planes gratuitos usados (condiciones verificadas en noviembre de 2026):

- **Neon** (PostgreSQL): sin vencimiento; 1 GB por proyecto y 100 horas de cómputo al mes; se suspende
  tras 5 minutos sin uso y se reactiva sola.
- **Render** (backend): el servicio se suspende tras 15 minutos sin tráfico y tarda cerca de un minuto
  en despertar; 750 horas gratis al mes. Se descartó su PostgreSQL gratuita porque vence a los 30 días.
- **GitHub Pages** (frontend).

### 5.1 Base de datos en Neon

1. Crea una cuenta en neon.com y un proyecto (región cercana, por ejemplo `AWS US East`).
2. En **Connect**, desactiva *Connection pooling* y copia la cadena de conexión
   (`postgresql://usuario:clave@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`).

### 5.2 Backend en Render

1. Sube el proyecto a GitHub (mismo repositorio de las entregas anteriores).
2. En render.com: **New → Web Service**, conecta el repositorio y configura:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3 (la versión se toma de `backend/.python-version`)
   - **Build Command:** `bash build.sh`
   - **Start Command:** `gunicorn config.wsgi:application`
   - **Instance Type:** Free
3. En **Environment** agrega:

   | Variable | Valor |
   |---|---|
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_SECRET_KEY` | una clave larga y aleatoria |
   | `DATABASE_URL` | la cadena de Neon |
   | `DB_SSL_REQUIRE` | `True` |
   | `CORS_ALLOWED_ORIGINS` | `https://claudiosgproyectos-max.github.io` |
   | `POS_CARGAR_DEMO` | `True` (opcional) |

4. **Create Web Service**. El build aplica migraciones y crea los usuarios. Verifica
   `https://NOMBRE-SERVICIO.onrender.com/api/salud/`.

### 5.3 Frontend en GitHub Pages

1. En `js/config.js` reemplaza `API_PRODUCCION` por `https://NOMBRE-SERVICIO.onrender.com/api/`.
2. Haz commit y push.
3. En GitHub: **Settings → Pages → Deploy from a branch**, rama `main`, carpeta `/ (root)`.
4. Abre https://claudiosgproyectos-max.github.io/lopez-rios-sanabria-mvp2-web-2026-2/ e inicia sesión.

## 6. Entrega

```powershell
powershell -ExecutionPolicy Bypass -File .\crear-zip.ps1
```

Genera `web-2026-2-mvp3-lopez-rios-sanabria.zip` sin `env`, `.venv`, `.git`, `__pycache__`,
`node_modules`, `.env` ni bases de datos locales.
