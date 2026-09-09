---
name: shopops-update
description: Handle an explicitly invoked request to safely update ShopOps Reporter while preserving local device and project state; do not use for initial installation or general diagnostics.
---

Act when explicitly invoked or when `shopops-onboard` identifies a required
update during an authorized onboarding request. Update one Reporter
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
5. Wait for explicit confirmation of the exact locked target version. Reuse
   existing authorization only when it covers this exact version and update;
   an unversioned request is not approval for an arbitrary target.
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

Reporter 0.5.0 adds contract schema v2. Deploy a backend advertising that schema first.
An upgrade preserves v1 contracts; it does not migrate or submit them. Migration is a separate
`result-contract migrate-schema --to v2` operation that creates a candidate and requires one
administrator review after submission. Ordinary source changes then reuse the approved v2
contract automatically; business meaning, mapping and reporting scope changes need a new version.
Never install a candidate build merely because this skill describes its capabilities; use the
published checksum-locked release selected by the installer.

Reporter 0.4.0 adds independent project metadata synchronization and current-device
ownership. Deploy a compatible ShopOps backend first. Existing YAML stays readable;
missing metadata is unknown, not a reason to reset project identity. The running
daemon synchronizes declared metadata without a business run. The update workflow
does not start it or edit project metadata. Explain `unsupported_server`, failed
sync and `pending_migration` separately from runtime health, using cached status.
An upgrade never authorizes device migration, local task termination, or SOP
execution-mode replacement.

## 完整接入能力（0.7 协议）

需要完整接入时，先读取 [能力接入与服务端回执](../../references/capability-onboarding.md)。遇到 APScheduler 时读取 [应用计划适配](../../references/apscheduler-integration.md)。保留旧项目基础上报；使用 capabilities check 区分配置、验收和本次接收。人工覆盖优先，角色自动绑定不要求逐项目管理员批准；定时映射保留原确认流程。升级软件不代表业务项目已完成适配。
