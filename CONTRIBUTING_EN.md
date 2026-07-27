# Contributing

Thanks for helping improve VulnFlanker.

## Local Checks

Run focused checks before sending a pull request:

```powershell
python -m compileall backend\app
$env:PYTHONPATH = "backend;backend/tests"
python -m pytest -q
cd frontend
npm install
npm run build
npm audit
cd ..\agent
go test ./...
cd ..\tools\watchvuln-collector
go test ./...
```

Optional security audits before a release:

```powershell
python -m pip install pip-audit
pip-audit
cd agent
govulncheck ./...
cd ..\tools\watchvuln-collector
govulncheck ./...
```

## Development Notes

- Keep changes scoped to the feature or bug being addressed.
- Do not commit local `.env` files, runtime state, build outputs, or private
  planning notes.
- Add or update tests for behavior changes.
- Keep public documentation self-contained; the public release is expected to
  work without private planning documents.
- Do not include real credentials, private infrastructure names, or proprietary
  vulnerability intelligence data in fixtures.

## Security Changes

For authentication, Agent ingress, encryption, verification execution, or
network exposure changes, include a short security impact note in the pull
request description.
