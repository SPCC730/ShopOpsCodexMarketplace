---
name: shopops-doctor
description: Handle an explicitly invoked WP1 request to diagnose ShopOps Reporter onboarding; do not use for general project diagnostics.
---

Act only after the developer explicitly invokes this skill. This is a read-only
WP1 diagnostic: never install, repair, delete, enroll, pair, or change runtime
state. Do not inspect, scan, connect, or execute a business project.

1. From the installed plugin directory, run
   `PYTHONPATH=tools python3 -m shopops_plugin_helper probe --json`. If the
   environment is unsupported, report `repair_required` with the probe reason.
2. Run
   `PYTHONPATH=tools python3 -m shopops_plugin_helper install-preview --json`.
   This verifies the selected macOS wheelhouse and its checksum inventory without
   installation. If it fails, report `repair_required` and preserve the error.
3. Inspect only the previewed Reporter home paths: the stable
   `<reporter-home>/bin/shopops-report` shim and its target, plus the target
   runtime's `venv/bin/shopops-report`. Do not inspect projects or any other
   user directories. Run the stable shim with `--json status` only when both
   files are present and executable.
4. Report exactly one state:
   - `not_installed`: no stable shim or no Reporter runtime is present.
   - `repair_required`: a shim target is malformed, missing, non-executable, or
     inconsistent with its runtime; the checksum preview or status JSON is invalid.
   - `upgrade_available`: the shim and its current runtime are healthy, but their
     installed version differs from the checksum-locked preview version.
   - `not_paired`: the current runtime and shim are healthy and status reports
     the Reporter unpaired state.
   - `healthy`: the current runtime and shim are healthy, match the previewed
     version, and status succeeds.

Include the probe, preview, inspected shim/target, and status evidence in the
report. Offer no silent repair or install; an install requires the separate
`shopops-onboard` preview-and-confirmation workflow. Reporter cleanup is a
separate explicit operation outside WP1 and must first preview affected runtime
versions, device identity, queued runs, and projects before confirmation.
Removing this Codex plugin does not remove Reporter, its device identity, queue,
or project launch capability. See [the security policy](../../references/security-policy.md).
