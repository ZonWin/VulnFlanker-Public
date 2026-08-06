# Changelog

## Unreleased

- Preparing the first public source release.
- Replaced base64-only AI API key storage with server-side encrypted storage
  backed by `VULNFLANKER_AI_KEY_ENCRYPTION_KEY`.
- Updated frontend routing dependency usage to remove current npm audit
  findings.
- Restored backend test collection by adding the shared matching test helper.
- Removed obsolete tracked backup/module files that should not ship publicly.

## 0.1.0

- Initial MVP baseline for vulnerability intelligence ingestion, asset
  inventory, asset-vulnerability matching, risk queue operations, read-only
  verification tasks, Agent ingress, and audit logging.
