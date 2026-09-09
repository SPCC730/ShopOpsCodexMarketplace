# Reporter upgrade activation and existing entrypoints

There are five independent version locations: plugin manifest, installed machine runtime, shell command resolution, running Reporter daemon, and task invocation (OS action/custom wrapper/business Python import). Installing a wheel changes only the machine runtime and stable shim. `status.reporter_version` identifies the CLI process, not necessarily its daemon.

Stable paths:

- macOS: `~/.shopops-reporter/bin/shopops-report`.
- Windows: `%LOCALAPPDATA%\ShopOps\Reporter\bin\shopops-report.cmd`.
- Standard `.shopops/run.command` and `run.ps1` already use those shims; their `windows-task-wrapper.ps1` forwards trigger context. Named tasks live under `.shopops/tasks/<task-key>/` and must retain `--task`.

Never use `runtime/0.6.0/venv/...` (or any versioned runtime) in a new permanent task action. PowerShell: `& $Reporter run ...`; batch: `call "...\bin\shopops-report.cmd" run ...` so exit-code propagation is preserved. Task Scheduler cannot directly treat a .cmd file as an executable: keep the existing PowerShell wrapper, or use cmd.exe with correct /d /s /c quoting after preview. Do not blindly substitute an exe with a cmd in a task XML Execute field.

## Inspection and repair

1. `activation-check` returns standard wrapper classifications without executing them. `stable_entrypoint` means the file matches the current generated template, **not** that an OS task actually points to it. A changed template is deliberately reported for review. Missing/inaccessible project paths and wrappers cannot count as verified.
2. On macOS inspect current user and explicitly applicable system launchd plist Program/ProgramArguments and loaded definitions; on Windows inspect the current user's relevant Task Scheduler actions. Inspect actual referenced wrappers only, not whole source/output trees. Do not output full XML/plists containing arguments/secrets. Record schedule ID, entrypoint path, state and whether a pinned Reporter reference was found.
3. Follow the execution chain to the actual Reporter invocation. Preserve the enclosing shell/Powershell, cwd, project path, task key, trigger variables and argument forwarding. An old path in comments is not proof of active use. Do not change the business `command` in integration.yaml merely because it names an old Python: that is the business environment, not necessarily Reporter.
4. Before edits, save private byte-for-byte backups and original file hashes; recheck hashes immediately before atomic replacement. Preview before/after Reporter path only. If a file changed concurrently, re-read and re-preview. Use the existing update authorization for proven Reporter-only changes.
5. Do not rewrite result-contract files, project identities, source fingerprints, schedule consent or launchd enabled state. Never replace all project wrappers with templates: custom behavior and task isolation must survive. If code fingerprint or schedule mapping changes due to a necessary custom wrapper edit, retain the normal project's schema/mapping rules and report the next required step.
6. For `python -m shopops_reporter`, `uv run shopops-report`, bare `shopops-report` or an imported bridge, establish the exact executable/environment. Use installed package metadata or a version-only check, never the business script. Prefer the stable wrapper for Reporter CLI calls; imported integrations require a separately reviewed environment dependency update. Keep unknown items pending.

## Acceptance without a business run

The `upgrade` helper resumes a verified old Reporter daemon and verifies its runtime; it leaves a stopped background alone unless `--start-background` is given. Foreign/stale PID reuse is never a reason to kill a process. An unavailable control endpoint blocks activation rather than forcing it.

After upgrading, use `activation-check`, the absolute stable shim's JSON status, current/new shell command resolution and a fresh server device heartbeat. Do not test wrapper changes by executing `run`, launching scheduled jobs, or restarting a business scheduler. Historical records correctly retain old versions. List a stopped background as inactive, and any unreviewed OS action/import as pending, not “all tasks upgraded”.
