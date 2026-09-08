---
name: shopops-onboard
description: Guide a developer who asks to onboard local scripts or a folder to ShopOps Reporter, including explicitly invoked installation, task selection, result contracts and resuming onboarding.
---

Use this as the single entrypoint when the developer asks to onboard to ShopOps
or provides a local script/folder for that purpose. A path alone in an unrelated
conversation is not an onboarding request. Installation-only requests still stop
after runtime health reporting. Project onboarding continues using
[the guided workflow](../../references/guided-onboarding.md).
Configuration does not authorize business execution; each real run retains its
own concrete task and command confirmation.

Start with the requested path and current runtime health. Reuse a healthy
installation and existing pairing. Use `shopops-doctor` for the read-only health
subflow and `shopops-update` when an update is needed; the developer need not
memorize or invoke each subskill. Existing authorization for the same concrete
operation remains valid; ask only for missing scope or a new operation.

The guided workflow is **unreleased** and requires local capability
`guided_onboarding: 1` and server `task_profiles: 1` / `onboarding_verification: 1`.
The bundled 0.4.2 wheels do not contain it. Check capabilities before preparing
tasks; report `upgrade_required` if unavailable. Do not create named-task files
with an older runtime or install an unpublished build as a fallback.

## Installation When Needed

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
   the exact previewed version before running any install command. A prior
   confirmation applies only if this exact version and operation were authorized.
4. Only after that confirmation, run `shopops_plugin_helper install
   --confirm-version <previewed-version> --json` with the same helper interpreter
   and `PYTHONPATH` selected in step 1.
   Do not substitute a different version. Report the returned runtime and stable
   shim paths.
5. Run the returned stable shim as
   `<shim-path> --json status` and show its JSON health result. A `not_paired`
   result is a valid installed-but-unpaired state; do not enroll or pair a device
   in WP1.

For an installation-only request, stop after installation and health reporting.
For project onboarding, continue the guided workflow once its capabilities are
available. Cleanup is a separate
explicit operation outside WP1 and must first preview affected runtime versions,
device identity, queued runs, and projects before confirmation. Removing this
Codex plugin does not remove Reporter, its device identity, queue, or project
launch capability. See [the security policy](../../references/security-policy.md).

## Project Dashboard Discovery

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
`shopops-report init`. Output-only script changes belong to the separately
previewed guided workflow. If the service is only
bound to loopback, report that it is not reachable from Run Center rather than
publishing an unusable URL.

## Project metadata and device ownership (Reporter 0.4.0+)

During an explicitly requested project onboarding, propose `display_name`,
`description`, optional `project_version`, and `run_mode` in the existing
`.shopops/integration.yaml`. Use project evidence and developer confirmation;
do not infer `manual` from an empty scan. Leave the mode `unknown` unless manual
or scheduled execution is established. Do not include secrets in these fields.
Preserve `project_key`, `integration_id`, descriptor and device identity across
ordinary code changes. The administrator-owned SOP name is independent of the
project name. One SOP uses either internal or external execution, not both.

After an authorized metadata change, `shopops-report --json sync --project-dir .`
reports the actual outcome. The running daemon independently synchronizes
registered project metadata every 60 seconds; `--json status` reads cached results
without contacting projects or the server. Upload policy/dashboard changes still
need explicit sync; result contract changes still need separate reviewed submission.
Do not treat an unsupported server or failed scan as a successful empty schedule.

Moving the original project configuration to another paired computer requests
`pending_migration`, not immediate upload permission. Keep the original project
identity. Have the developer stop the old scripts and task schedules and drain
the old upload queue before the administrator activates the new device in External
Access. This confirmation is not proof of remote process termination; never claim
that ShopOps stopped the old computer. Historical runs and other projects remain.
