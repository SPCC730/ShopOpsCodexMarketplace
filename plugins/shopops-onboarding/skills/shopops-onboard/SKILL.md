---
name: shopops-onboard
description: Handle an explicitly invoked WP1 request to onboard a local script project to ShopOps Reporter; do not use for general ShopOps assistance.
---

Act only after the developer explicitly invokes this skill. WP1 installs the local
Reporter runtime only; it does not inspect, scan, connect, or execute a business
project, and it does not enroll a device.

1. From the installed plugin directory, run the helper with an available Python
   interpreter. On macOS use
   `PYTHONPATH=tools python3 -m shopops_plugin_helper probe --json`. On Windows
   PowerShell set `$env:PYTHONPATH = "tools"` and use the installed `py` launcher
   or `python` command. Report the JSON result and stop if
   `environment.supported` is false. WP1 accepts CPython 3.11 and newer Python 3
   versions on Apple Silicon macOS and Windows x64; the current offline release
   has wheelhouses for 3.11 through 3.14.
2. Run `shopops_plugin_helper install-preview --json` with the same helper
   interpreter and `PYTHONPATH` selected in step 1.
   This validates the checksum-locked offline wheelhouse and reports the exact
   Reporter version, runtime directory, stable shim, and whether a change is
   needed. Explain that the installer uses `pip --no-index` and never contacts
   PyPI.
3. Show the complete preview, including the version and paths. 等待开发者明确确认
   the exact previewed version before running any install command. Do not infer
   confirmation from the original request or from a prior confirmation.
4. Only after that confirmation, run `shopops_plugin_helper install
   --confirm-version <previewed-version> --json` with the same helper interpreter
   and `PYTHONPATH` selected in step 1.
   Do not substitute a different version. Report the returned runtime and stable
   shim paths.
5. Run the returned stable shim as
   `<shim-path> --json status` and show its JSON health result. A `not_paired`
   result is a valid installed-but-unpaired state; do not enroll or pair a device
   in WP1.

Stop after installation and health reporting. For safety, cleanup is a separate
explicit operation outside WP1 and must first preview affected runtime versions,
device identity, queued runs, and projects before confirmation. Removing this
Codex plugin does not remove Reporter, its device identity, queue, or project
launch capability. See [the security policy](../../references/security-policy.md).
