"""Run with the installed Reporter Python; never execute a project launcher."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path


def classify_launcher(content: str, expected: str) -> str:
    if content.replace("\r\n", "\n") == expected.replace("\r\n", "\n"):
        return "stable_entrypoint"
    if re.search(r"runtime[/\\]+[^/\\\s]+[/\\]+venv", content, re.IGNORECASE):
        return "pinned_runtime"
    if re.search(r"(?:-m\s+shopops_reporter|shopops-report(?:\.exe|\.cmd)?)", content):
        return "custom_entrypoint_review_required"
    return "unknown_entrypoint"


def inspect() -> dict:
    from shopops_reporter import __version__
    from shopops_reporter.config import reporter_home
    from shopops_reporter.daemon_control import (
        inspect_daemon,
        process_identity,
        read_marker,
    )
    from shopops_reporter.project import write_launchers
    from shopops_reporter.schedule_map import registered_tasks

    daemon = inspect_daemon()
    daemon["runtime_version"] = None
    if daemon["state"] == "healthy":
        # inspect_daemon authenticates the local control endpoint. Recheck the
        # process identity before interpreting its invocation, never expose argv.
        _, marker = read_marker()
        process = process_identity(daemon["pid"])
        if marker and process and all(marker[k] == process[k] for k in ("pid", "created_at", "executable")):
            command = process["command"]
            try:
                import psutil
                # macOS framework Python rewrites argv[0] to the system
                # executable; its venv launcher remains in this one variable.
                executable = psutil.Process(daemon["pid"]).environ().get("__PYVENV_LAUNCHER__") or command[0]
                # Resolve directory aliases (/var vs /private/var), but never
                # resolve the python symlink itself out of its virtualenv.
                invoked = Path(executable)
                relative = (invoked.parent.resolve() / invoked.name).relative_to(reporter_home().resolve() / "runtime")
                if len(relative.parts) == 4 and tuple(p.lower() for p in relative.parts[1:3]) in (("venv", "bin"), ("venv", "scripts")):
                    daemon["runtime_version"] = relative.parts[0]
            except (IndexError, ValueError, psutil.Error):
                pass
    entries = []
    registry = reporter_home() / "projects.json"
    declared_projects = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else []
    if not isinstance(declared_projects, list) or any(not isinstance(p, str) for p in declared_projects):
        raise ValueError("project_registry_invalid")
    unavailable = [p for p in declared_projects if not Path(p).is_dir()]
    # This registry is explicit. Do not crawl source trees, logs or output files.
    for task in registered_tasks():
        with tempfile.TemporaryDirectory(prefix="shopops-launcher-template-") as folder:
            root = Path(folder)
            write_launchers(root, task_key=task.task_key)
            template = root / ".shopops"
            if task.task_key:
                template = template / "tasks" / task.task_key
            for name in ("run.command", "run.ps1", "windows-task-wrapper.ps1"):
                path = task.config_dir / name
                state = "missing"
                try:
                    if path.is_symlink() or not path.resolve().is_relative_to(task.root.resolve()):
                        state = "unsafe_path"
                    elif path.is_file():
                        state = classify_launcher(path.read_text(encoding="utf-8-sig"), (template / name).read_text(encoding="utf-8"))
                except (OSError, UnicodeError):
                    state = "unreadable"
                entries.append({"path": str(path), "task_key": task.task_key, "state": state})
    return {
        "installed_version": __version__, "daemon": daemon, "launchers": entries,
        "unavailable_projects": unavailable,
        "scheduler_actions": "review_required",
        "shell_path": "review_required",
        "project_python_imports": "review_required",
    }


def stop_authenticated() -> dict:
    import psutil
    from shopops_reporter.daemon_control import inspect_daemon, request_daemon_stop

    state = inspect_daemon()
    if state["state"] != "healthy":
        raise RuntimeError("daemon_not_verified")
    process = psutil.Process(state["pid"])
    try:
        request_daemon_stop()
    except RuntimeError:
        # Reporter 0.6/0.7's stop command waits only five seconds. Windows
        # read-only scheduler collection can still be finishing. Never force
        # termination; wait for this same process to finish naturally.
        pass
    process.wait(timeout=45)
    if inspect_daemon()["state"] not in {"stopped", "stale"}:
        raise RuntimeError("daemon_changed_during_stop")
    return {"stopped": True}


if __name__ == "__main__":
    import sys
    print(json.dumps(stop_authenticated() if sys.argv[1:] == ["stop"] else inspect()))
