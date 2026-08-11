# Dev: sube Docker, espera servicios, aplica migraciones y arranca uvicorn con recarga.
$ErrorActionPreference = "Stop"
$RepoRoot = Join-Path $PSScriptRoot ".."
Set-Location -LiteralPath $RepoRoot

Write-Host "Levantando servicios (PostgreSQL + Redis)..."
docker compose up -d

Write-Host "Esperando a que los servicios estén sanos..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    $dbOk = (docker inspect --format="{{.State.Health.Status}}" carbargains-db 2>$null) -eq "healthy"
    $redisOk = (docker inspect --format="{{.State.Health.Status}}" carbargains-redis 2>$null) -eq "healthy"
    if ($dbOk -and $redisOk) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Error "Los servicios no están sanos a tiempo. Revisa: docker compose ps"
}

$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

Write-Host "Aplicando migraciones..."
& $VenvPython -m alembic -c backend\alembic.ini upgrade head

Write-Host "Arrancando API en http://localhost:8000 (docs: /docs)"
& $VenvPython -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
