---
name: shopops-onboard
description: Handle an explicitly invoked WP1 request to onboard a local script project to ShopOps Reporter; do not use for general ShopOps assistance.
---

Act only after the developer explicitly invokes this skill. The installation part
is WP1 and installs the local Reporter runtime only. A separate, explicitly
requested project-onboarding step may read the selected project for existing
ShopOps declarations; it never executes business code or connects to a dashboard.

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

## Project dashboard discovery (explicit request only)

When the developer explicitly asks to onboard a project after WP1 is healthy,
first confirm the working directory is the intended project. Read only
`.shopops/dashboard.json`, common HTML report files, and an explicit report URL
from a startup command as a candidate for review. Never infer a dashboard from
an arbitrary `BaseUrl`, API endpoint, or browser URL.

The declaration must be one of:

```json
{"version":1,"kind":"html","title":"业务看板","path":"reports/index.html"}
```

or:

```json
{"version":1,"kind":"live_service","title":"业务看板","url":"http://127.0.0.1:9540/"}
```

Validate that a live service is HTTP, has a port, has no credentials, query,
or fragment, and points to a private/loopback address. Explain that a service
must listen on a LAN interface (`0.0.0.0` or the developer's LAN IP) for the
ShopOps Run Center to open it. Show the candidate and its exact source, then
wait for confirmation before writing `.shopops/dashboard.json` or running
`shopops-report init`. Do not modify business scripts. If the service is only
bound to loopback, report that it is not reachable from Run Center rather than
publishing an unusable URL.
