import json
import re
from pathlib import Path

import yaml


PLUGIN_ROOT = Path("plugins/shopops-onboarding")
SKILLS_ROOT = PLUGIN_ROOT / "skills"
SKILL_SPECS = {
    "shopops-onboard": "onboard",
    "shopops-doctor": "diagnose",
}
FORBIDDEN_SKILL_ACTIONS = (
    re.compile(
        r"\b(?:run|execute|scan|inspect|analy[sz]e|modify|write)\b"
        r"\s+(?:(?:the|a|an|this|that|local)\s+)?(?:project|script)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:run|execute|invoke|trigger|start)\b\s+(?:the\s+)?"
        r"(?:shopops\s+)?reporter\b(?:\s+(?:business\s+)?"
        r"(?:run|workflow|job|report))?",
        re.IGNORECASE,
    ),
    re.compile(r"(?:运行|执行|扫描|查看|检查|分析|修改|写|写入|编写)\s*(?:本地\s*)?(?:项目|脚本)"),
    re.compile(r"(?:运行|执行|调用|触发|启动)\s*(?:ShopOps\s*)?Reporter(?:\s*(?:业务|任务|工作流|运行))?"),
)


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


def test_wp1_skills_require_explicit_invocation_and_stop_without_project_actions():
    for skill_name, expected_scope in SKILL_SPECS.items():
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
        assert expected_scope in description
        assert "[todo:" not in contents.lower()

        paragraphs = [paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()]
        normalized_body = body.lower()
        assert len(paragraphs) == 2
        assert "act only after the user explicitly invokes this skill." in normalized_body
        assert "wp1 does not yet provide" in normalized_body
        assert "then stop without inspecting or modifying a project." in normalized_body
        assert not any(pattern.search(body) for pattern in FORBIDDEN_SKILL_ACTIONS)
