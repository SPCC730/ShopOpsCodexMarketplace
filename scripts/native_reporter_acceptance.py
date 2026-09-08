"""Exercise a released wheel using synthetic files and a temporary Windows task."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import yaml

from shopops_reporter.config import ProjectConfig
from shopops_reporter.onboarding import workflow
from shopops_reporter.onboarding.discovery import discover
from shopops_reporter.project import project_fingerprint
from shopops_reporter.result_mapping.policy import reporting_policy
from shopops_reporter.schedule_map import save_schedule_map
from shopops_reporter.scheduler import WindowsTaskScheduler, schedule_key
from shopops_reporter.task_context import TaskContext, atomic_json


class FixtureServer:
    def __init__(self):
        self.integration_id = str(uuid4())
        self.contract = None

    def signed_get(self, path):
        if path.endswith("/capabilities"):
            return {"task_profiles": 1, "onboarding_verification": 1,
                    "result_contract_schemas": ["shopops.result_contract.v2"]}
        assert path.endswith("/status")
        return {"onboarding": {"integration_status": "active", "binding_status": "active",
                              "contract": self.contract}}

    def signed_json(self, method, path, payload):
        assert method == "POST"
        if path.endswith("/resolve"):
            return {"integration_id": self.integration_id, "project_key": payload["project_key"],
                    "descriptor": {"task_scope": payload["task_scope"]},
                    "descriptor_signature": "synthetic", "created": True}
        assert path.endswith("/result-contracts")
        self.contract = {"id": str(uuid4()), "version": 1, "digest": payload["digest"],
                         "status": "approved"}
        return self.contract


def powershell(script, env=None):
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            env=env, capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def main():
    # macOS exposes /tmp through a symlink; discovery intentionally rejects
    # symlinked ancestors, so keep the fixture under the real workspace path.
    fixture_parent = Path.cwd() / ".acceptance-tmp"
    fixture_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ShopOps acceptance ", dir=fixture_parent) as directory:
        root = Path(directory)
        entry = root / "main.py"
        entry.write_text(
            "import json\nfrom pathlib import Path\n"
            "p = Path('output/result.json')\np.parent.mkdir(exist_ok=True)\n"
            "count = json.loads(p.read_text())['count'] + 1 if p.exists() else 1\n"
            "p.write_text(json.dumps({'headline':'Fixture checked','status':'ok','count':count}))\n"
        )
        server = FixtureServer()
        discovered = discover(root)
        state = workflow.prepare(root, {"tasks": [{"entry": "main.py"}]},
                                 scope_digest=discovered["digest"])
        sid, key = state["session_id"], state["tasks"][0]["task_key"]
        context = TaskContext(root, key)
        spec = {"name": "Native acceptance", "platform": "fixture",
                "command": [sys.executable, "main.py"], "result_json": "output/result.json"}
        plan = workflow.preview(sid, key, "initialize", spec)
        workflow.apply(sid, plan["plan_id"], plan["digest"], client=server)
        config = ProjectConfig.load(root, task_key=key)
        samples = []
        for status in ("completed", "partial", "no_change", "failed"):
            relative = context.relative_config(f"result-samples/{status}.json")
            atomic_json(root / relative, {"status": status})
            samples.append({"name": status, "business_status": status, "fixture": relative})
        contract = {
            "schema": "shopops.result_contract.v2", "name": "Native fixture",
            "business_meaning": "Checks a synthetic local output",
            "reporting_policy": reporting_policy(config),
            "sources": {"result": {"type": "json", "path": "output/result.json"}},
            "summary": {"headline": {"source": "result", "selector": "/headline"}},
            "business_status": {"value": {"source": "result", "selector": "/status"},
                                "mapping": {"ok": "completed"}, "default": "failed"},
            "metrics": [], "details": [], "claims": [], "artifacts": [], "samples": samples,
        }
        context.contract_path.write_text(yaml.safe_dump(contract), encoding="utf-8")
        plan = workflow.preview(sid, key, "submit")
        workflow.apply(sid, plan["plan_id"], plan["digest"], client=server)
        plan = workflow.preview(sid, key, "run")
        result = workflow.apply(sid, plan["plan_id"], plan["digest"], client=server)
        assert result["task"]["exit_code"] == 0
        assert json.loads((root / "output/result.json").read_text())["count"] == 1
        assert workflow.check(sid, key, client=server)["phase"] == "report_pending"
        assert workflow.apply(sid, plan["plan_id"], plan["digest"], client=server)["already_applied"]

        if os.name == "nt":
            name = "ShopOps-Acceptance-" + uuid4().hex
            native_key = schedule_key(name, "\\")
            config = ProjectConfig.load(root, task_key=key)
            save_schedule_map(root, {"version": 1, "mappings": [{
                "schedule_key": native_key, "task_name": name,
                "project_fingerprint": project_fingerprint(root, config=config),
                "integration_id": config.integration_id, "accepted": True,
            }]}, task_key=key)
            env = {**os.environ, "SHOPOPS_ACCEPTANCE_ROOT": str(root),
                   "SHOPOPS_ACCEPTANCE_WRAPPER": str(context.file("windows-task-wrapper.ps1")),
                   "SHOPOPS_ACCEPTANCE_NAME": name, "SHOPOPS_ACCEPTANCE_KEY": native_key}
            try:
                powershell(
                    "$ErrorActionPreference='Stop'; "
                    "$argv='-NoProfile -File \"'+$env:SHOPOPS_ACCEPTANCE_WRAPPER+'\" -TaskKey '+$env:SHOPOPS_ACCEPTANCE_KEY; "
                    "$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argv "
                    "-WorkingDirectory $env:SHOPOPS_ACCEPTANCE_ROOT; "
                    "Register-ScheduledTask -TaskName $env:SHOPOPS_ACCEPTANCE_NAME -Action $action | Out-Null",
                    env,
                )
                scan = WindowsTaskScheduler().scan()
                assert scan.complete, scan.error
                task = next(item for item in scan.tasks if item["task_name"] == name)
                assert len(task["projects"]) == 1
                assert task["projects"][0]["integration_id"] == config.integration_id
                powershell("Start-ScheduledTask -TaskName $env:SHOPOPS_ACCEPTANCE_NAME", env)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if json.loads((root / "output/result.json").read_text())["count"] == 2:
                        break
                    time.sleep(0.25)
                else:
                    raise RuntimeError("native_task_did_not_execute_named_launcher")
            finally:
                powershell(
                    "Unregister-ScheduledTask -TaskName $env:SHOPOPS_ACCEPTANCE_NAME -Confirm:$false -ErrorAction SilentlyContinue",
                    env,
                )
        print(json.dumps({"guided_onboarding": "passed", "platform": sys.platform,
                          "native_task_scheduler": "passed" if os.name == "nt" else "not_applicable"}))


if __name__ == "__main__":
    main()
