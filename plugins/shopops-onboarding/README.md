# ShopOps Onboarding

`shopops-onboarding` provides the WP1 local installation and diagnosis path for
ShopOps Reporter. It is available only for macOS Apple Silicon with CPython 3.11
or 3.12, using the plugin's checksum-locked offline wheelhouse. The installer
uses `pip --no-index` and never contacts PyPI.

## Skills

- `shopops-onboard` probes the environment, previews the locked Reporter
  version and paths, waits for explicit developer confirmation, installs that
  exact version, and reports `shopops-report --json status`.
- `shopops-doctor` probes, validates the locked preview, inspects only the
  Reporter runtime and stable shim, and reports `healthy`, `not_installed`,
  `not_paired`, `upgrade_available`, or `repair_required`. It never repairs or
  changes runtime state.

WP1 does not scan, connect to, or execute business projects, and it does not
enroll devices. It contains no MCP service, UI, browser extension, lifecycle
hook, cleanup command, publish, push, or merge workflow.

Removing this Codex plugin does not remove Reporter, its device identity, queue,
or project launch capability. Reporter cleanup is a separate explicit operation
outside WP1 and must preview affected runtime versions, identity, queued runs,
and projects before explicit confirmation. See
[the security policy](references/security-policy.md).
