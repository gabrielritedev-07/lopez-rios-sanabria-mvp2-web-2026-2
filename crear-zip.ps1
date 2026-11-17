# Genera el ZIP de entrega del MVP 3 sin dependencias, entornos virtuales, .git ni archivos pesados.
# Uso (desde la carpeta del proyecto):  powershell -ExecutionPolicy Bypass -File .\crear-zip.ps1
$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$nombre = "web-2026-2-mvp3-lopez-rios-sanabria"

# 1. Exporta el esquema SQL generado por las migraciones (si el entorno virtual existe).
$python = Join-Path $raiz "backend\env\Scripts\python.exe"
if (Test-Path $python) {
    $carpetaSql = Join-Path $raiz "backend\sql"
    New-Item -ItemType Directory -Force -Path $carpetaSql | Out-Null
    $manage = Join-Path $raiz "backend\manage.py"
    $sql = foreach ($app in "usuarios", "catalogo", "compras", "ventas", "faltantes", "caja") {
        $migraciones = Get-ChildItem (Join-Path $raiz "backend\apps\$app\migrations") -Filter "0*.py" | Sort-Object Name
        foreach ($migracion in $migraciones) {
            "-- ===== $app / $($migracion.BaseName) ====="
            & $python $manage sqlmigrate $app $migracion.BaseName
        }
    }
    $sql | Out-File -FilePath (Join-Path $carpetaSql "esquema.sql") -Encoding utf8
    Write-Host "Esquema SQL exportado en backend\sql\esquema.sql"
}

# 2. Copia el proyecto a una carpeta temporal excluyendo lo que no se entrega.
$temp = Join-Path $env:TEMP $nombre
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
robocopy $raiz $temp /E `
    /XD .git .venv env venv node_modules __pycache__ staticfiles dist build .vscode .idea apps-script `
    /XF .env *.pyc *.sqlite3 *.zip `
    /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falló con código $LASTEXITCODE" }

# 3. Comprime.
$zip = Join-Path $raiz "$nombre.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $temp "*") -DestinationPath $zip
Remove-Item $temp -Recurse -Force

$tamano = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host "ZIP creado: $zip ($tamano MB)"
