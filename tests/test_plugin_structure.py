import json
from pathlib import Path


def test_marketplace_points_to_plugin():
    marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text())
    assert marketplace["name"] == "shopops-internal"
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/shopops-onboarding"


def test_manifest_exposes_only_two_skills_and_no_hooks():
    manifest = json.loads(
        Path("plugins/shopops-onboarding/.codex-plugin/plugin.json").read_text()
    )
    assert manifest["name"] == "shopops-onboarding"
    assert manifest["skills"] == "./skills/"
    assert "hooks" not in manifest
