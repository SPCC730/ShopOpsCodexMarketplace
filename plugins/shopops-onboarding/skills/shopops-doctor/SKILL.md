---
name: shopops-doctor
description: Handle an explicitly invoked WP1 request to diagnose ShopOps Reporter onboarding; do not use for general project diagnostics.
---

For Reporter 0.5.0 projects, inspect the active result_contract.file reference within the
selected task directory. Contract schema v2 does not bind approval to source fingerprints:
source-only drift is not a reason to regenerate or re-review it. Diagnose
result_contract_reporting_policy_mismatch as a changed reporting scope requiring a new
contract. Diagnose result_contract_digest_changed as an unsubmitted local contract edit.
v1 still uses the old source binding; suggest a separately confirmed migrate-schema --to v2
flow for one-time review. Do not migrate, submit or run a project during diagnosis.

Act when explicitly invoked or used as the read-only health subflow of an
authorized `shopops-onboard` request. This is a read-only
WP1 diagnostic: never install, repair, delete, enroll, pair, or change runtime
state. Do not inspect, scan, connect, or execute a business project. Dashboard
discovery belongs to the separate explicit project-onboarding step in
`shopops-onboard`, never to this diagnostic.

1. From the installed plugin directory, run the helper with an available Python
   interpreter. On macOS use
   `PYTHONPATH=tools python3 -m shopops_plugin_helper probe --json`. On Windows
   PowerShell set `$env:PYTHONPATH = "tools"` and use the installed `py` launcher
   or `python` command. The probe accepts CPython 3.11 and newer Python 3
   versions; the current offline release has wheelhouses for 3.11 through 3.14.
   If the environment is unsupported, report `repair_required` with the probe
   reason.
2. Run `shopops_plugin_helper install-preview --json` with the same helper
   interpreter and `PYTHONPATH`. This verifies the selected platform wheelhouse
   and its checksum inventory without installation. If it fails, report
   `repair_required` and preserve the error.
3. Inspect only the previewed Reporter home paths. On macOS these are the stable
   `<reporter-home>/bin/shopops-report` shim and the target runtime's
   `venv/bin/shopops-report`. On Windows these are
   `<reporter-home>\bin\shopops-report.cmd` and the target runtime's
   `venv\Scripts\shopops-report.cmd`. Do not inspect projects or any other user
   directories. Validate the shim before any status command and require exact canonical content
   for the selected platform. The macOS shim must have the
   canonical `#!/bin/sh` and `exec <expected-runtime-binary> "$@"`
   content. The Windows shim must call only
   `%~dp0..\runtime\<active-version>\venv\Scripts\shopops-report.cmd`, and that
   runtime launcher may set only `PYTHONUTF8=1` before invoking
   `%~dp0python.exe -m shopops_reporter %*`.
   Resolve
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

For Reporter 0.4.0+, separately report each registered project's cached `sync`
state. `failed`, `unsupported_server`, and `pending_migration` are not successful
project synchronization, even when the runtime itself is healthy. Use the cached
association, device, scan status and freshness only; do not run `sync` or scan
project files. A fresh project heartbeat does not make an old scan current.
For pending migration, explain that the old scripts/schedules must be stopped
and uploads drained before administrator activation. Do not perform migration.

Include the probe, preview, inspected shim/target, and status evidence in the
report. Offer no silent repair or install; an install requires the separate
`shopops-onboard` preview-and-confirmation workflow. Reporter cleanup is a
separate explicit operation outside WP1 and must first preview affected runtime
versions, device identity, queued runs, and projects before confirmation.
Removing this Codex plugin does not remove Reporter, its device identity, queue,
or project launch capability. See [the security policy](../../references/security-policy.md).

## 完整接入能力（0.7 协议）

需要完整接入时，先读取 [能力接入与服务端回执](../../references/capability-onboarding.md)。遇到 APScheduler 时读取 [应用计划适配](../../references/apscheduler-integration.md)。保留旧项目基础上报；使用 capabilities check 区分配置、验收和本次接收。人工覆盖优先，角色自动绑定不要求逐项目管理员批准；定时映射保留原确认流程。升级软件不代表业务项目已完成适配。


## Installed versus active version

After validating the current locked runtime, use `shopops_plugin_helper activation-check --json` to compare installed version with the authenticated daemon runtime and audit standard launchers. A healthy old daemon or pinned task wrapper is not a fully updated installation. The CLI status version is not the daemon version. Read [upgrade activation](../../references/upgrade-activation.md); route requested repairs to `shopops-update`. Preserve unreviewed scheduler actions, shell PATH and imported business environments as pending checks.
