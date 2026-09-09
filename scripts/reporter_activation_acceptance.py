"""Real old-daemon/new-install activation; loopback-only synthetic device."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
plugin = repo / "plugins/shopops-onboarding"
sys.path.insert(0, str(plugin / "tools"))
from shopops_plugin_helper.activation import activation_check, upgrade_reporter
from shopops_plugin_helper.environment import probe_environment, platform_key
from shopops_plugin_helper.installer import install_reporter


def run(args, env):
    return subprocess.run([str(a) for a in args], env=env, check=True, capture_output=True, text=True).stdout


with tempfile.TemporaryDirectory(prefix="shopops-activation-") as folder:
    home = Path(folder) / "reporter"
    home.mkdir()
    os.environ["SHOPOPS_REPORTER_PORT"] = "0"
    env = {**os.environ, "SHOPOPS_REPORTER_HOME": str(home)}
    probe = probe_environment([sys.executable])
    old = home / "runtime/0.6.0/venv"
    run([sys.executable, "-m", "venv", old], env)
    python = old / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheels = plugin / "wheelhouse" / platform_key(probe.os_name, probe.architecture) / f"cp{sys.version_info.major}{sys.version_info.minor}"
    run([python, "-m", "pip", "install", "--no-index", "--find-links", wheels, repo / "tests/fixtures/upgrade/shopops_reporter-0.6.0-py3-none-any.whl"], env)
    install_reporter(plugin, home, probe)
    # Current wheel installed, previous daemon running: the original failure.
    run([python, "-c", "from shopops_reporter.config import reporter_home; from shopops_reporter.client import generate_private_key; import json; h=reporter_home(); h.joinpath('device.json').write_text(json.dumps(dict(server_url='http://127.0.0.1:9',device_id='activation-fixture',installation_id='activation-fixture',display_name='activation-fixture',declared_operator=None,private_key_storage='file'))); h.joinpath('device.key').write_text(generate_private_key()[0])"], env)
    try:
        run([python, "-m", "shopops_reporter", "--json", "start"], env)
        before = activation_check(plugin, home, probe)
        assert before["installed_version"] == "0.7.0"
        assert before["daemon"]["runtime_version"] == "0.6.0", before
        assert not before["activation_verified"]
        result = upgrade_reporter(plugin, home, probe)
        assert result["restarted"]
        assert result["activation"]["activation_verified"]
        assert result["activation"]["daemon"]["pid"] != before["daemon"]["pid"]
        again = upgrade_reporter(plugin, home, probe)
        assert not again["restarted"]
        assert again["activation"]["daemon"]["pid"] == result["activation"]["daemon"]["pid"]
        shim = Path(result["install"]["shim_path"])
        shim.write_text("stale entrypoint\n", encoding="utf-8")
        assert not activation_check(plugin, home, probe)["activation_verified"]
        repaired = upgrade_reporter(plugin, home, probe)
        assert repaired["install"]["changed"]
        assert repaired["activation"]["activation_verified"]
        assert not repaired["restarted"]
        assert python.exists()
        print(json.dumps({"python": sys.version.split()[0], "old_daemon": "0.6.0", "new_daemon": "0.7.0", "idempotent": True, "business_executed": False}))
    finally:
        run([python, "-m", "shopops_reporter", "--json", "stop"], env)
