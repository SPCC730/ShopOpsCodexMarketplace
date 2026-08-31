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
   user directories. Validate the shim before any status command: it must have
   the exact canonical content `#!/bin/sh` followed by
   `exec <expected-runtime-binary> "$@"`, where the expected binary is
   `<reporter-home>/runtime/<active-version>/venv/bin/shopops-report`. Resolve
   that target, ensure it is an executable regular file under
   `<reporter-home>/runtime/`, and reject symlink escapes or any other target.
   Compare the installed runtime version in that contained target with the
   checksum-locked preview version. If they differ, do not run its status command:
   an older Reporter status is not guaranteed to be read-only. Report
   `upgrade_available` and stop. Continue only for the exact locked version.
   Run the validated runtime binary directly with `--json status`; never execute
   the shim during diagnosis. Require schema `shopops.reporter.cli.v1`, the matching
   `reporter_version`, action `status`, and consistent exit-code/`ok` semantics.
   Accept only exit 0 with `ok: true` and a data object, or exit 2 with
   `ok: false` and error code `not_paired`.
4. Apply these states in order and report exactly one:
   - `not_installed`: only when both the stable shim and every Reporter runtime
     are absent.
   - `repair_required`: any partial, malformed, missing-target, or
     non-executable shim/runtime artifact; a target outside the expected runtime;
     or an invalid checksum preview or same-version status JSON.
   - `upgrade_available`: the shim and its current runtime are healthy, but their
     installed version differs from the checksum-locked preview version; do not
     invoke that older runtime's status command.
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
