# VulnFlanker

Chinese version: [README.md](README.md)

VulnFlanker is a vulnerability impact assessment and controlled verification
platform for internal security operations. It connects vulnerability
intelligence, host asset snapshots, asset-vulnerability matching, risk
prioritization, read-only verification tasks, and audit logs into one workflow.

The first public release is a `v0.1` baseline. It is useful for local demos,
internal trials, and small controlled environments. It is not a hardened
internet-facing production stack.

## Documentation

| Document | Chinese | English |
| --- | --- | --- |
| Project overview | [README.md](README.md) / [Chinese copy](Documents/README_ZH.md) | [README_EN.md](README_EN.md) |
| Changelog | [CHANGELOG_ZH.md](Documents/CHANGELOG_ZH.md) | [CHANGELOG_EN.md](Documents/CHANGELOG_EN.md) |
| Contributing guide | [CONTRIBUTING_ZH.md](Documents/CONTRIBUTING_ZH.md) | [CONTRIBUTING_EN.md](Documents/CONTRIBUTING_EN.md) |
| Security policy | [SECURITY_ZH.md](Documents/SECURITY_ZH.md) | [SECURITY_EN.md](Documents/SECURITY_EN.md) |
| Third-party notices | [THIRD_PARTY_NOTICES_ZH.md](Documents/THIRD_PARTY_NOTICES_ZH.md) | [THIRD_PARTY_NOTICES_EN.md](Documents/THIRD_PARTY_NOTICES_EN.md) |
| Open source release review | [OPEN_SOURCE_RELEASE_REVIEW_ZH.md](Documents/OPEN_SOURCE_RELEASE_REVIEW_ZH.md) | [OPEN_SOURCE_RELEASE_REVIEW_EN.md](Documents/OPEN_SOURCE_RELEASE_REVIEW_EN.md) |

## What It Does

- Collects and normalizes vulnerability intelligence from CISA KEV, Aliyun AVD,
  and the built-in WatchVuln collector.
- Receives Linux host snapshots from the Agent ingress API.
- Tracks assets, components, network exposure, Agent status, and snapshot
  freshness.
- Evaluates whether a vulnerability affects an asset through product, version,
  operating-system, feature, and exposure rules.
- Produces risk queue entries with priority, risk factors, explanations, and
  stable risk codes.
- Creates read-only verification tasks and records Agent-returned evidence.
- Provides a React console for assets, vulnerabilities, matching results, risk
  operations, verification tasks, AI settings, platform settings, and audit logs.
- Supports AI-assisted vulnerability information enrichment through configurable
  providers.

## Architecture

```text
Vulnerability feeds
        |
        v
Intel collection -> normalization -> vulnerability catalog
        |                                  |
        |                                  v
Linux Agent -> Agent ingress -> assets -> matching engine -> risk queue
        ^                                  |
        |                                  v
        +--------- verification tasks <- match detail
```

Main runtime services:

- Console API: authenticated control-plane API under `/api/v1`.
- Agent Ingress: Agent-facing API under `/agent/v1`.
- Worker and Beat: background jobs for collection, enrichment, and monitoring.
- PostgreSQL and Redis: persistence and task queue infrastructure.
- Frontend: Vite-built React console served behind Nginx in the demo compose
  stack.

## Quick Start

Requirements:

- Docker and Docker Compose
- PowerShell, Bash, or another shell capable of copying `.env.example`
- Internet access if you want to collect live vulnerability intelligence

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting:

- Set `VULNFLANKER_REDIS_PASSWORD` to a non-default value.
- Set `VULNFLANKER_INTEL_WEBHOOK_TOKEN` to a non-default value.
- Set `VULNFLANKER_AI_KEY_ENCRYPTION_KEY` before saving AI provider API keys.
- Leave `VULNFLANKER_BOOTSTRAP_ADMIN_PASSWORD` empty if you want to use the
  first-run setup page.

Start the demo stack:

```powershell
docker compose --env-file .env -f .\deploy\docker-compose.yml up --build -d
```

Open the console:

```text
http://127.0.0.1:8100/
```

Useful local service URLs:

- Console API health: `http://127.0.0.1:8000/api/v1/health/live`
- Agent Ingress health: `http://127.0.0.1:8001/agent/v1/health/live`

The compose file in `deploy/docker-compose.yml` is intentionally optimized for
demo and development use. It uses source bind mounts and reload-enabled backend
processes.

## Agent

The Linux host Agent lives in `agent/` and is written in Go. It collects local
asset information, reports heartbeats, pulls read-only verification tasks, and
returns verification evidence.

Build the Agent:

```powershell
cd agent
go build ./cmd/vulnflanker-agent
```

The console can generate enrollment tokens and installation commands. New
deployments should use `/agent/v1`; the legacy Agent API compatibility switch is
kept on for v0.1 only.

## AI Enrichment

AI enrichment is optional. Built-in fake profiles are available for deterministic
local tests. Real providers can be configured in the console.

When saving a real provider API key, set:

```env
VULNFLANKER_AI_KEY_ENCRYPTION_KEY=<long-random-secret>
```

New AI keys are stored with encrypted `fernet:` storage. Legacy `b64:` and
`plain:` stored values remain readable for migration compatibility. Back up the
encryption key: losing it makes stored AI keys unrecoverable.

## Local Development

Backend checks:

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "backend;backend/tests"
python -m compileall backend\app
python -m pytest -q
```

Frontend checks:

```powershell
cd frontend
npm install
npm run build
npm audit
```

Go checks:

```powershell
cd agent
go test ./...
cd ..\tools\watchvuln-collector
go test ./...
```

## Repository Layout

```text
backend/                    Console API, Agent Ingress, services, tests
frontend/                   React console
agent/                      Linux host Agent
tools/watchvuln-collector/  Built-in WatchVuln collector
deploy/                     Demo/development Docker files
Documents/                  Chinese and English project documentation
.github/                    CI and dependency update configuration
```

Private planning notes, internal docs, and real third-party vulnerability corpus
captures are intentionally not part of the public release branch.

## Security Boundary

- Do not expose the console API, Agent Ingress, PostgreSQL, or Redis directly to
  the public internet.
- Put HTTPS, authentication boundaries, network access control, and monitoring in
  front of any shared deployment.
- Rotate all example passwords, webhook tokens, Redis passwords, bootstrap
  passwords, Agent secrets, and AI encryption keys.
- Set secure cookies behind HTTPS by enabling
  `VULNFLANKER_SESSION_COOKIE_SECURE=true`.
- Agent Bearer Secret authentication exists, but HMAC replay protection and
  secret rotation are future hardening items.
- Current verification tasks are read-only. Automatic remediation and intrusive
  proof-of-concept execution are intentionally out of scope for v0.1.

See [`Documents/SECURITY_EN.md`](Documents/SECURITY_EN.md) for vulnerability
reporting guidance.

## License

VulnFlanker is licensed under the Apache License, Version 2.0. See `LICENSE` and
`NOTICE` for details.
