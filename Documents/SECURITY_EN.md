# Security Policy

VulnFlanker is currently a v0.9.0-prep preparation release intended for local
demos, internal testing, and small controlled environments.

## Supported Versions

| Version | Supported |
| --- | --- |
| v0.9.0-prep | Security fixes are accepted before the first stable release. |

## Reporting a Vulnerability

Please do not open a public issue for sensitive security reports.

For the first public release, report vulnerabilities through GitHub private
vulnerability reporting if it is enabled on the repository. If it is not enabled
yet, contact the project maintainers using the repository owner profile.

Reports should include:

- Affected version or commit.
- A clear description of the issue.
- Reproduction steps or proof-of-concept details.
- Impact and suggested remediation, if known.

## Deployment Warning

Do not expose the console API, Agent Ingress, PostgreSQL, or Redis directly to
the public internet. Shared or production-like deployments should use HTTPS,
network access control, rotated credentials, secure cookies, and external
monitoring.
