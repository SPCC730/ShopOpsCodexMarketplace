import json
from pathlib import Path
import tomllib

import yaml


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SKILL_SCOPES = {"shopops-onboard": "onboard", "shopops-doctor": "diagnose"}


def test_marketplace_exposes_only_the_expected_plugin_with_approved_policy():
    marketplace = json.loads(Path(".agents/plugins/marketplace.json").read_text())
    assert marketplace["name"] == "shopops-internal"
    assert marketplace["plugins"] == [
        {
            "name": "shopops-onboarding",
            "source": {
                "source": "local",
                "path": "./plugins/shopops-onboarding",
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            "category": "Developer Tools",
        }
    ]


def test_manifest_exposes_the_required_skill_path_without_runtime_components():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin/plugin.json").read_text())
    assert manifest["name"] == "shopops-onboarding"
    assert manifest["version"] == "0.1.7"
    assert manifest["skills"] == "./skills/"
    assert set(manifest).isdisjoint(
        {
            "hooks",
            "mcpServers",
            "apps",
            "assets",
            "scripts",
            "lifecycle",
            "lifecycleScripts",
            "onInstall",
            "onUse",
            "onUninstall",
            "preInstall",
            "postInstall",
            "preUninstall",
            "postUninstall",
        }
    )
    assert {".codex-plugin", "skills"}.issubset(
        {path.name for path in PLUGIN_ROOT.iterdir()}
    )


def test_plugin_has_only_the_two_wp1_skill_entrypoints():
    assert {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()} == {
        "shopops-onboard",
        "shopops-doctor",
    }


def test_wp1_skills_preserve_the_approved_safe_frontmatter_contract():
    for skill_name, scope in SKILL_SCOPES.items():
        contents = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert contents.startswith("---\n"), f"{skill_name} must have YAML frontmatter"
        frontmatter_end = contents.find("\n---\n", 4)
        assert frontmatter_end != -1, f"{skill_name} frontmatter must be closed"

        frontmatter = yaml.safe_load(contents[4:frontmatter_end])
        body = contents[frontmatter_end + 5 :]

        assert isinstance(frontmatter, dict)
        assert set(frontmatter) == {"name", "description"}
        assert frontmatter["name"] == skill_name
        assert isinstance(frontmatter["description"], str)
        description = frontmatter["description"].lower()
        assert description.strip()
        assert "shopops reporter" in description
        assert "explicitly invoked" in description
        assert scope in description
        assert "[todo:" not in contents.lower()

        assert "Act only after the developer explicitly invokes this skill." in body
        assert "business" in body and "project" in body


def test_wp1_skills_keep_the_required_authorization_and_retention_boundaries():
    onboard = (SKILLS_ROOT / "shopops-onboard" / "SKILL.md").read_text(encoding="utf-8")
    doctor = (SKILLS_ROOT / "shopops-doctor" / "SKILL.md").read_text(encoding="utf-8")

    assert "install-preview" in onboard
    assert "等待开发者明确确认" in onboard
    assert onboard.index("等待开发者明确确认") < onboard.index("--confirm-version")
    assert "never install, repair, delete, enroll, pair, or change runtime" in doctor
    for text in (onboard, doctor):
        assert "Removing this" in text
        assert "Codex plugin does not remove Reporter" in text
        assert "device identity, queued runs, and projects before confirmation" in text


def test_root_pytest_collects_root_and_plugin_helper_suites():
    configuration = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert configuration["tool"]["pytest"]["ini_options"]["testpaths"] == [
        "tests",
        "plugins/shopops-onboarding/tests",
    ]
