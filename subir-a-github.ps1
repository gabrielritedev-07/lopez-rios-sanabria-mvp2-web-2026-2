# Sube el proyecto al repositorio del equipo en GitHub.
# Uso (desde la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File .\subir-a-github.ps1
#
# Sirve para la primera subida y para todas las siguientes. Qué hace:
# 1. Conecta la carpeta con el repositorio (si estaba conectada a otro, cambia el remoto).
# 2. La primera vez toma el historial que ya tenga el repositorio en GitHub, sin tocar tus archivos.
# 3. Prepara los cambios y verifica que NO se suban secretos, entornos virtuales ni bases locales.
# 4. Verifica que estén las migraciones que Render necesita.
# 5. Hace commit, integra lo que hayan subido tus compañeros y hace push a main.

$repo = "https://github.com/claudiosgproyectos-max/lopez-rios-sanabria-mvp2-web-2026-2.git"
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
    $nombre = Read-Host "Tu nombre para los commits (ej. Claudio Sanabria)"
    $correo = Read-Host "El correo de tu cuenta de GitHub"
    git config --global user.name $nombre
    git config --global user.email $correo
}
Write-Host "Commits a nombre de: $(git config user.name) <$(git config user.email)>"

# 1. Conectar con el repositorio
if (-not (Test-Path ".git")) {
    Ejecutar "Inicializando repositorio local" { git init -b main }
}
$remotoActual = git remote get-url origin 2>$null
if (-not $remotoActual) {
    Ejecutar "Agregando el repositorio de GitHub" { git remote add origin $repo }
} elseif ($remotoActual -ne $repo) {
    Write-Host "La carpeta apuntaba a: $remotoActual" -ForegroundColor Yellow
    Ejecutar "Cambiando al repositorio nuevo" { git remote set-url origin $repo }
}

Ejecutar "Consultando el repositorio en GitHub (puede pedir iniciar sesión)" { git fetch origin }
$hayMainRemoto = [bool](git ls-remote --heads origin main)

# 2. Primera vez con este repositorio: tomar su historial sin modificar los archivos locales
if ($hayMainRemoto) {
    git rev-parse --verify --quiet HEAD *> $null
    $tieneCommits = ($LASTEXITCODE -eq 0)
    $base = $null
    if ($tieneCommits) { $base = git merge-base HEAD origin/main 2>$null }
    if (-not $base) {
        Ejecutar "Tomando el historial de GitHub (tus archivos no cambian)" { git reset origin/main }
    }
}
git branch -M main 2>$null

# 3. Preparar cambios y bloquear archivos privados o pesados
Ejecutar "Preparando cambios" { git add -A }
$preparados = @(git diff --cached --name-only)
$privados = $preparados | Where-Object {
    $_ -match '(^|/)\.env$' -or $_ -match '^backend/env/' -or $_ -match '^\.venv' -or
    $_ -match '__pycache__' -or $_ -match '\.sqlite3$' -or $_ -match '^lopez-rios-sanabria-mvp2-web-2026-2'
}
if ($privados) {
    git reset | Out-Null
    Fallar "Se iban a subir archivos privados o pesados:`n$($privados -join "`n")`nRevisa el .gitignore antes de continuar."
}

# 4. Migraciones necesarias en Render
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

# 5. Commit, integrar cambios de compañeros y push
if ($preparados.Count -gt 0) {
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
} else {
    Write-Host "No hay archivos nuevos; se revisará si quedó algo pendiente por subir." -ForegroundColor Yellow
}

if ($hayMainRemoto) {
    Write-Host "-> Integrando lo que hayan subido tus compañeros" -ForegroundColor Cyan
    git pull --rebase origin main
    if ($LASTEXITCODE -ne 0) {
        Fallar "Hay conflictos con cambios de tus compañeros. Resuélvelos en VS Code (pestaña Control de código fuente), luego ejecuta 'git rebase --continue' y vuelve a correr este script."
    }
}
Ejecutar "Subiendo a GitHub" { git push -u origin main }

Write-Host ""
Write-Host "Listo. Revisa: https://github.com/claudiosgproyectos-max/lopez-rios-sanabria-mvp2-web-2026-2" -ForegroundColor Green
