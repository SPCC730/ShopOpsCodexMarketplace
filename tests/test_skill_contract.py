from pathlib import Path


PLUGIN_ROOT = Path("plugins/shopops-onboarding")


def onboard_skill_text() -> str:
    return (PLUGIN_ROOT / "skills/shopops-onboard/SKILL.md").read_text(encoding="utf-8")


def doctor_skill_text() -> str:
    return (PLUGIN_ROOT / "skills/shopops-doctor/SKILL.md").read_text(encoding="utf-8")


def test_onboard_requires_confirmation_between_preview_and_install():
    text = onboard_skill_text()
    assert "install-preview" in text
    assert "等待开发者明确确认" in text
    assert text.index("等待开发者明确确认") < text.index("--confirm-version")


def test_skills_do_not_contain_hooks_or_automatic_project_execution():
    assert "shopops-report run" not in onboard_skill_text()
    assert "自动运行" not in doctor_skill_text()
