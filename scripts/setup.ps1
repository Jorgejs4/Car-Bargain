# Setup del backend: venv (Python 3.12), dependencias, .env y Playwright.
$ErrorActionPreference = "Stop"
$RepoRoot = Join-Path $PSScriptRoot ".."
Set-Location -LiteralPath $RepoRoot

if (-not (Test-Path -LiteralPath "backend\.venv")) {
    Write-Host "Creando venv con Python 3.12..."
    py -3.12 -m venv backend\.venv
}

$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

Write-Host "Actualizando pip..."
& $VenvPython -m pip install --upgrade pip

Write-Host "Instalando dependencias..."
& $VenvPython -m pip install -r backend\requirements-dev.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Write-Host "Creando .env desde .env.example..."
    Copy-Item ".env.example" ".env"
}

Write-Host "Instalando navegador de Playwright (chromium)..."
& $VenvPython -m playwright install chromium

Write-Host "Setup completado. Siguiente: scripts\dev.ps1"
