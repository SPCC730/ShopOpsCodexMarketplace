import json
from pathlib import Path

import yaml


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SKILL_SPECS = {
    "shopops-onboard": {
        "scope": "onboard",
        "body": (
            "Act only after the user explicitly invokes this skill.",
            "WP1 does not yet provide an automated project connection workflow. "
            "Tell the user that ShopOps Reporter onboarding is unavailable in WP1, "
            "then stop without inspecting or modifying a project.",
        ),
    },
    "shopops-doctor": {
        "scope": "diagnose",
        "body": (
            "Act only after the user explicitly invokes this skill.",
            "WP1 does not yet provide onboarding diagnostics. Tell the user that "
            "ShopOps Reporter diagnostics are unavailable in WP1, then stop without "
            "inspecting or modifying a project.",
        ),
    },
}


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
    assert {path.name for path in PLUGIN_ROOT.iterdir()} == {".codex-plugin", "skills"}


def test_plugin_has_only_the_two_wp1_skill_entrypoints():
    assert {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()} == {
        "shopops-onboard",
        "shopops-doctor",
    }


def test_wp1_skills_match_the_approved_safe_body_contract():
    for skill_name, expected in SKILL_SPECS.items():
        contents = (SKILLS_ROOT / skill_name / "SKILL.md").read_text()
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
        assert expected["scope"] in description
        assert "[todo:" not in contents.lower()

        paragraphs = tuple(
            paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()
        )
        assert paragraphs == expected["body"]
