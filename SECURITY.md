# Security Policy

## Supported Versions

The latest minor release line is supported with security fixes. Older lines receive fixes at the maintainer's discretion.

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

Please report security issues privately via **admin@dominusaxis.com** or through GitHub's private vulnerability reporting:
<https://github.com/Tgbjr2025/stash-plex-bridge/security/advisories/new>.

Include:

- A description of the issue and its impact
- Steps to reproduce (minimal PoC preferred)
- Affected version(s) and platform
- Any suggested remediation

You will receive an acknowledgement within 72 hours. We aim to publish a fix or coordinated disclosure within 30 days of validated reports.

## Supply Chain

- All releases are built from a tagged commit via GitHub Actions.
- Build provenance is attested via [sigstore](https://www.sigstore.dev/) (`actions/attest-build-provenance`).
- Each release ships a `SHA256SUMS.txt` alongside the artifacts — verify before running.
- Commits are GPG-signed by the maintainer.

## Scope

In scope:
- Code in this repository
- Releases published to this repository

Out of scope:
- Vulnerabilities in upstream Stash, Plex, or third-party plugins
- Issues requiring local admin or physical access
- Social-engineering attacks
