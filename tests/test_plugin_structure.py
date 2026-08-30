import json
import re
from pathlib import Path


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
SKILLS_ROOT = PLUGIN_ROOT / "skills"


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
    assert manifest["skills"] == "./skills/"
    assert set(manifest).isdisjoint(
        {
            "hooks",
            "mcpServers",
            "apps",
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
    assert {path.name for path in PLUGIN_ROOT.iterdir()} == {".codex-plugin", "skills"}


def test_plugin_has_only_the_two_wp1_skill_entrypoints():
    assert {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()} == {
        "shopops-onboard",
        "shopops-doctor",
    }


def test_wp1_skills_require_explicit_invocation_and_stop_without_project_actions():
    expected_scopes = {
        "shopops-onboard": "onboard",
        "shopops-doctor": "diagnose",
    }

    for skill_name, expected_scope in expected_scopes.items():
        contents = (SKILLS_ROOT / skill_name / "SKILL.md").read_text()
        frontmatter_match = re.match(
            r"^---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z",
            contents,
            re.DOTALL,
        )

        assert frontmatter_match, f"{skill_name} must have YAML frontmatter"
        frontmatter = frontmatter_match.group("frontmatter")
        body = frontmatter_match.group("body").lower()
        name_match = re.search(r"^name: (.+)$", frontmatter, re.MULTILINE)
        description_match = re.search(r"^description: (.+)$", frontmatter, re.MULTILINE)

        assert name_match and name_match.group(1) == skill_name
        assert description_match
        description = description_match.group(1).lower()
        assert "shopops reporter" in description
        assert "explicitly invoked" in description
        assert expected_scope in description
        assert "[TODO:" not in contents
        assert "act only after the user explicitly invokes this skill." in body
        assert "wp1 does not yet provide" in body
        assert "then stop without inspecting or modifying a project." in body
        assert "scan" not in body
        assert "execut" not in body
