---
name: shopops-update
description: Handle an explicitly invoked request to safely update ShopOps Reporter while preserving local device and project state; do not use for initial installation or general diagnostics.
---

Act only after the developer explicitly invokes this skill. Update one Reporter
installation on the current computer. Never update another machine, run business
scripts, re-enroll the device, or change project business code.

1. From the installed plugin directory, run the same environment probe and
   checksum-locked `install-preview --json` used by `shopops-onboard`. Use an
   available CPython 3.11-3.14 interpreter that matches Apple Silicon macOS or
   Windows x64. If either check fails, report `repair_required` and stop.
2. Inspect only the standard Reporter home returned by the preview. Determine
   the active shim target and installed Reporter version without executing an
   older runtime. Read only sanitized state: whether device metadata exists,
   counts from the Reporter queue, and the registered project summaries. Never
   display or copy a private key, pairing code, Cookie, Token, complete identity
   file, project secret, command environment, or business output.
3. If the installed version equals the locked version, validate the canonical
   shim and run that exact runtime's `--json status`. Report `healthy`,
   `not_paired`, or `repair_required`; do not reinstall a healthy current
   version.
4. If the installed version differs, report `upgrade_available` and show the
   current version, locked target version, platform, Python ABI, runtime and shim
   paths, pairing-preservation status, queue counts, registered project count,
   and these update boundaries:
   - installs a new versioned runtime and atomically repoints the stable shim;
   - preserves device identity, `.shopops` project configuration, project
     registry, old runtime, and offline queue;
   - does not re-pair, re-upload, modify, synchronize, or run a project.
5. Wait for explicit confirmation of the exact locked target version. Do not
   treat the original request, a previous confirmation, or an unversioned
   confirmation as approval.
6. After confirmation, run `shopops_plugin_helper install --confirm-version
   <locked-version> --json` with the same interpreter and `PYTHONPATH`. Do not
   use PyPI or substitute another version. If installation fails, preserve the
   previous shim/runtime and report `repair_required` with the helper error.
7. Validate the returned canonical shim, then run the new exact runtime's
   `--json status`. Compare device identity presence, queue counts, and project
   registry with the pre-update summary. Report any mismatch instead of trying
   to recreate state.
8. List projects that may need a separate `shopops-report sync`: only projects
   whose dashboard declaration, result/artifact rules, launch command, or
   Windows wrapper/mapping changed. Do not run `sync` or any business script.
   Remind the developer to start a new Codex task after a plugin update so the
   updated skill definitions are loaded.

Removing or updating this Codex plugin does not remove Reporter, its device
identity, queue, or project launch capability. Reporter cleanup is a separate
explicit operation and must preview all affected state before confirmation.
