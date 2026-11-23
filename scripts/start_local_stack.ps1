# SSRI hybrid local stack: Compose Postgres + host Redis + Poetry API/worker.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Upsert local .env SSRI_* keys =="
& "$Root\model\.venv\Scripts\python.exe" "$Root\scripts\upsert_local_env.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Stop stale Compose API/worker (keep postgres) =="
docker stop ssri-api ssri-worker ssri-recovery ssri-redis ssri-minio 2>$null | Out-Null

Write-Host "== Start Compose Postgres (host Redis assumed on :6379) =="
docker compose -f infra/docker-compose.yml up -d postgres
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Wait for Postgres =="
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    docker exec ssri-postgres pg_isready -U ssri -d ssri 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Write-Error "Postgres did not become ready"; exit 1 }

Write-Host "== Stop stale host uvicorn/celery =="
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -match 'uvicorn.*ssri_model\.api\.app' -or
      $_.CommandLine -match 'celery.*ssri_model\.worker'
    )
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "== Bootstrap Stage 2.5 registry (NOT_VALIDATED; synthetic if needed) =="
& "$Root\model\.venv\Scripts\python.exe" "$Root\scripts\bootstrap_local_stage25_registry.py" --activate
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Registry bootstrap failed — offline assess needs a checkpoint later."
}

$logDir = Join-Path $Root "data\outputs\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$apiOut = Join-Path $logDir "api.out.log"
$apiErr = Join-Path $logDir "api.err.log"
$workerOut = Join-Path $logDir "worker.out.log"
$workerErr = Join-Path $logDir "worker.err.log"

Write-Host "== Start API =="
$api = Start-Process -FilePath "$Root\model\.venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","ssri_model.api.app:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory "$Root\model" `
  -RedirectStandardOutput $apiOut `
  -RedirectStandardError $apiErr `
  -PassThru `
  -WindowStyle Hidden

Start-Sleep -Seconds 5

Write-Host "== Start Celery worker (solo pool for Windows) =="
$worker = Start-Process -FilePath "$Root\model\.venv\Scripts\python.exe" `
  -ArgumentList "-m","celery","-A","ssri_model.worker.celery_app","worker","--loglevel=info","-Q","ssri_jobs","--concurrency=1","--pool=solo" `
  -WorkingDirectory "$Root\model" `
  -RedirectStandardOutput $workerOut `
  -RedirectStandardError $workerErr `
  -PassThru `
  -WindowStyle Hidden

Start-Sleep -Seconds 6
Write-Host "API PID=$($api.Id)  WORKER PID=$($worker.Id)"
Write-Host "Logs: $apiErr | $workerErr"

try {
  $health = Invoke-WebRequest "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 30
  Write-Host "HEALTH $($health.Content)"
  $readyBody = (Invoke-WebRequest "http://127.0.0.1:8000/api/v1/ready" -UseBasicParsing -TimeoutSec 60).Content
  Write-Host "READY $readyBody"
} catch {
  Write-Warning "Health/ready probe failed: $($_.Exception.Message)"
  Write-Host "Check $apiErr"
}

Write-Host @"

Local stack started.
  API docs:   http://127.0.0.1:8000/docs
  Frontend:   cd frontend; npm run dev
  Demo mode:  must stay false (SSRI_DEMO_MODE=false)
  Science:    NOT_VALIDATED until independent validation
"@
