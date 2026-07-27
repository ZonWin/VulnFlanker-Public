# VulnFlanker Open Source Release Review

This checklist tracks the work needed before publishing the first open source
release. The `docs/` directory is expected to be removed from the public
release, so public-facing instructions must be self-contained in root-level
files such as `README.md`.

## Current Readiness

Status: public worktree content prepared for v0.1 release.

The project now passes the main local quality gates after the first round of
high-priority fixes. The current branch removes private planning material,
internal docs, and real third-party vulnerability corpus captures from the
public worktree.

Important: if the existing repository is made public with its full Git history,
previous commits may still expose files that were removed in this branch. For a
clean public launch, publish this branch through a clean-history repository or
history-scrubbed release process.

## Release Blockers

- [x] Remove tracked internal working notes.
  - Tracked paths include `.planning/`, `task_plan.md`, `findings.md`,
    `progress.md`, and `README-old.md`.
  - These paths are now ignored and removed from Git tracking for the public
    branch while remaining available in the local working copy.

- [x] Make `README.md` self-contained after `docs/` is removed.
  - The README no longer links to private `docs/` paths.
  - It now includes project scope, architecture, quick start, Agent notes, AI
    encryption configuration, local checks, repository layout, and security
    boundaries.

- [x] Fix backend test collection.
  - Added the missing shared test helper and refreshed stale matching/migration
    fixtures.
  - Full backend tests now collect and pass locally.

- [x] Resolve frontend dependency audit findings.
  - Replaced the vulnerable React Router package path with the current
    `react-router` package and refreshed `package-lock.json`.
  - `npm audit` now reports zero vulnerabilities.

- [x] Review real vulnerability corpus redistribution.
  - Removed `backend/tests/fixtures/watchvuln_real_corpus` from public tracking.
  - Replaced it with minimal public-safe synthetic fixtures under
    `backend/tests/fixtures/public_watchvuln_corpus`.
  - Replaced real-corpus AI evaluation samples with public synthetic samples
    under `backend/tests/fixtures/public_ai_enrichment_eval`.

## High Priority Before v0.1 Public Release

- [x] Replace base64-only AI API key storage with real server-side encryption.
  - The previous implementation stored keys with a reversible `b64:` prefix.
  - New and updated keys are written with encrypted `fernet:` storage.
  - Legacy `b64:`/`plain:` values remain readable for migration compatibility.
  - Document that losing the encryption key makes stored AI keys unrecoverable.
  - Any entry point that saves an AI key, including backend scripts, now needs
    `VULNFLANKER_AI_KEY_ENCRYPTION_KEY`.

- [x] Clearly label `deploy/docker-compose.yml` as demo/development or split a
  production-oriented compose file.
  - Current compose uses `uvicorn --reload`, bind mounts `..:/workspace`, and
    includes fixed local Postgres credentials.
  - This is acceptable for demo usage but should not be presented as production
    hardening.

- [x] Remove tracked backup and confusing root module files.
  - `deploy/backend.Dockerfile.BAK` should not ship.
  - Root `go.mod` declares `module vulnflanker/a1`, while real Go modules live
    under `agent/` and `tools/watchvuln-collector/`.

- [x] Add basic open source project files.
  - `SECURITY.md` for vulnerability disclosure.
  - `CONTRIBUTING.md` for local setup, test commands, and contribution rules.
  - `CHANGELOG.md` for the first release note.
  - GitHub Actions CI for backend, frontend, and Go modules.
  - Dependabot or equivalent dependency update automation.

- [x] Generate or document third-party dependency notices.
  - Existing project license is Apache-2.0.
  - The built-in WatchVuln collector already has a third-party notice for
    adapted MIT-licensed logic.
  - Added root `THIRD_PARTY_NOTICES.md` and linked it from `NOTICE`.
  - Added non-blocking CI dependency audit coverage for Python and Go, while
    keeping `npm audit` as a blocking frontend check.

## Security Notes To Keep Public

- The current release is suitable for local demo, internal testing, and small
  controlled environments.
- Do not expose the console API, Agent Ingress, PostgreSQL, or Redis directly to
  the public internet.
- Use HTTPS and set secure cookies for shared or production-like deployments.
- Replace all example passwords, webhook tokens, Redis passwords, and bootstrap
  admin credentials.
- Agent Bearer Secret authentication exists, but HMAC replay protection and
  secret rotation are still future hardening items.
- No automatic remediation or intrusive proof-of-concept execution is included
  in the current release.

## Verification Snapshot

Commands already run during this review:

- `python -m alembic heads`: single Alembic head.
- `python -m compileall backend/app`: passed.
- `python -m pytest -q`: passed, 215 tests.
- Public synthetic corpus tests: passed.
- `npm run build`: passed.
- `npm audit`: passed, zero vulnerabilities.
- `go test ./...` in `agent/`: passed.
- `go test ./...` in `tools/watchvuln-collector/`: passed.
- `git diff --check`: passed, with Windows line-ending warnings only.
- Python dependency vulnerability audit and Go `govulncheck` are configured as
  non-blocking CI checks for the first public release branch.

## Suggested Fix Order

1. Re-run full local verification on the final branch.
2. Review the staged diff for accidentally exposed private names or data.
3. Publish through a clean-history public repository if old private files must
   not appear in Git history.
4. Tag `v0.1.0` from the clean public release state.
