$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = (Resolve-Path "$root\backend").Path

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
  & $venvPython -m celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=INFO
} else {
  python -m celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=INFO
}
