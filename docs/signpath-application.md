# SignPath.io OSS Application

SignPath.io offers free EV-grade Authenticode signing for open-source projects.
This is the cleanest free path to a SmartScreen-clean Windows installer.

## Apply

Form: https://signpath.io/open-source

**Suggested application text:**

> **Project name**: stash-plex-bridge
> **Repository**: https://github.com/Tgbjr2025/stash-plex-bridge
> **License**: MIT
> **Maintainer**: Thomas Bateman (admin@dominusaxis.com)
>
> **What it does**: Idempotent PowerShell installer that wires three
> Stash↔Plex synchronisation plugins into a working end-to-end setup on
> Windows. Auto-detects installs, extracts tokens, renders config, validates.
>
> **Why we need signing**: Current self-signed Authenticode certificate triggers
> Windows "Unknown Publisher" warnings. Package-manager distribution (winget,
> Chocolatey, Scoop) solves the default case, but users installing from the
> raw GitHub release hit the warning. SignPath OSS signing would let us
> publish a trusted `install.ps1` alongside the package-manager channels.
>
> **Security posture**:
> - GPG-signed commits (key 45E3BABE58983A29)
> - CodeQL security scanning on every PR
> - OpenSSF Scorecard auto-assessment
> - Dependabot weekly dependency updates
> - Private vulnerability reporting enabled
> - SLSA build-provenance attestation via sigstore
>
> **Release frequency**: Ad-hoc, expect ~monthly. Low-churn project.
>
> **Contact for signing requests**: admin@dominusaxis.com

## Once approved

SignPath supplies a GitHub Actions signing step. Replace the self-signed section
of `.github/workflows/release.yml` with:

```yaml
- name: Sign with SignPath
  uses: signpath/github-action-submit-signing-request@v1
  with:
    api-token: ${{ secrets.SIGNPATH_API_TOKEN }}
    organization-id: ${{ secrets.SIGNPATH_ORG_ID }}
    project-slug: stash-plex-bridge
    signing-policy-slug: release-signing
    artifact-configuration-slug: install-ps1
    github-artifact-id: ${{ steps.upload.outputs.artifact-id }}
    wait-for-completion: true
    output-artifact-directory: signed
```

Expected review time: 1–2 weeks.
