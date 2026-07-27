$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = (Resolve-Path "$root\backend").Path

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
  & $venvPython -m alembic upgrade head
} else {
  python -m alembic upgrade head
}
