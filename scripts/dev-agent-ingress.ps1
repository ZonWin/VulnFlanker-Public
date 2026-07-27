$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = (Resolve-Path "$root\backend").Path

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$hostAddress = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$port = if ($env:PORT) { $env:PORT } else { "8001" }
if (Test-Path $venvPython) {
  & $venvPython -m uvicorn app.main_agent:app --reload --host $hostAddress --port $port
} else {
  python -m uvicorn app.main_agent:app --reload --host $hostAddress --port $port
}
