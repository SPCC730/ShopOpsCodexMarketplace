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


def test_doctor_validates_a_contained_canonical_shim_before_running_status():
    text = doctor_skill_text()

    validation = "Validate the shim before any status command"
    execution = "Run the validated runtime binary directly"
    assert validation in text
    assert "exact canonical content" in text
    assert "under\n   `<reporter-home>/runtime/`" in text
    assert text.index(validation) < text.index(execution)
    assert text.index(execution) < text.index("--json status")
    assert "Run the stable shim with `--json status`" not in text


def test_doctor_state_precedence_reserves_not_installed_for_clean_absence():
    text = doctor_skill_text()

    assert "Apply these states in order" in text
    assert "`not_installed`: only when both the stable shim and every Reporter" in text
    assert "`repair_required`: any partial, malformed, missing-target, or" in text
    state_rules = text[text.index("Apply these states in order") :]
    assert state_rules.index("`not_installed`") < state_rules.index("`repair_required`")
