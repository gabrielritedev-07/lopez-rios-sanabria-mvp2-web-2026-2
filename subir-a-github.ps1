# Sube el proyecto al repositorio del equipo en GitHub, conservando el historial del MVP 2.
# Uso (desde la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File .\subir-a-github.ps1
#
# Qué hace:
# 1. Si la carpeta aún no es un repositorio Git, la conecta con el repositorio existente
#    sin modificar ningún archivo local.
# 2. Prepara todos los cambios y verifica que NO se suban secretos ni entornos virtuales.
# 3. Verifica que estén las migraciones que Render necesita.
# 4. Hace el commit y el push a la rama main.

$repo = "https://github.com/gabrielritedev-07/lopez-rios-sanabria-mvp2-web-2026-2.git"
Set-Location $PSScriptRoot

function Fallar($mensaje) {
    Write-Host ""
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

function Ejecutar($descripcion, [scriptblock]$comando) {
    Write-Host "-> $descripcion" -ForegroundColor Cyan
    & $comando
    if ($LASTEXITCODE -ne 0) { Fallar "Falló: $descripcion" }
}

# 0. Git instalado y con nombre y correo configurados
git --version | Out-Null
if ($LASTEXITCODE -ne 0) { Fallar "Git no está instalado. Descárgalo de https://git-scm.com y vuelve a ejecutar." }
if (-not (git config user.email)) {
    $nombre = Read-Host "Tu nombre para los commits (ej. Gabriel Ríos)"
    $correo = Read-Host "El correo de tu cuenta de GitHub"
    git config --global user.name $nombre
    git config --global user.email $correo
}
Write-Host "Commits a nombre de: $(git config user.name) <$(git config user.email)>"

# 1. Conectar con el repositorio existente (solo la primera vez)
if (-not (Test-Path ".git")) {
    Ejecutar "Inicializando repositorio local" { git init -b main }
    Ejecutar "Agregando el repositorio de GitHub" { git remote add origin $repo }
    Ejecutar "Descargando el historial del MVP 2" { git fetch origin }
    Ejecutar "Tomando el historial (tus archivos no cambian)" { git reset origin/main }
    Ejecutar "Siguiendo la rama main de GitHub" { git branch --set-upstream-to=origin/main main }
}

# 2. Preparar cambios y bloquear archivos privados
Ejecutar "Preparando cambios" { git add -A }
$preparados = @(git diff --cached --name-only)
$privados = $preparados | Where-Object {
    $_ -match '(^|/)\.env$' -or $_ -match '^backend/env/' -or $_ -match '^\.venv/' -or
    $_ -match '__pycache__' -or $_ -match '\.sqlite3$'
}
if ($privados) {
    git reset | Out-Null
    Fallar "Se iban a subir archivos privados o pesados:`n$($privados -join "`n")`nRevisa el .gitignore antes de continuar."
}

# 3. Migraciones necesarias en Render
$requeridas = @(
    "backend/apps/caja/migrations/0001_initial.py",
    "backend/apps/catalogo/migrations/0002_*.py",
    "backend/apps/ventas/migrations/0002_*.py"
)
foreach ($patron in $requeridas) {
    if (-not (Get-ChildItem $patron -ErrorAction SilentlyContinue)) {
        git reset | Out-Null
        Fallar "Falta la migración $patron. Ejecuta antes: python manage.py makemigrations catalogo ventas caja"
    }
}

if ($preparados.Count -eq 0) {
    Write-Host "No hay cambios nuevos para subir." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Archivos que se van a subir: $($preparados.Count)" -ForegroundColor Green
git status --short | Select-Object -First 40
if ($preparados.Count -gt 40) { Write-Host "... y $($preparados.Count - 40) más" }
Write-Host ""

$mensaje = Read-Host "Mensaje del commit (Enter = 'MVP 3: backend Django + PostgreSQL y frontend con JWT')"
if (-not $mensaje) { $mensaje = "MVP 3: backend Django + PostgreSQL y frontend con JWT" }

$confirmar = Read-Host "¿Subir a GitHub ahora? (s/n)"
if ($confirmar -notin @("s", "S", "si", "sí", "SI")) {
    Write-Host "Cancelado. Los cambios quedaron preparados (git add) pero no se subió nada."
    exit 0
}

Ejecutar "Creando commit" { git commit -m $mensaje }
Ejecutar "Subiendo a GitHub (puede abrir el navegador para iniciar sesión)" { git push -u origin main }

Write-Host ""
Write-Host "Listo. Revisa: https://github.com/gabrielritedev-07/lopez-rios-sanabria-mvp2-web-2026-2" -ForegroundColor Green
