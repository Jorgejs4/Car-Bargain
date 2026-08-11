# One-shot: prueba el scraping live de mobile.de desde la IP actual.
# Ejecuta `scrape_mobile_de_once.py` con el venv y pasa los argumentos recibidos.
$ErrorActionPreference = "Stop"
$RepoRoot = Join-Path $PSScriptRoot ".."
$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "backend\scripts\scrape_mobile_de_once.py"

& $VenvPython $Script @args
exit $LASTEXITCODE
