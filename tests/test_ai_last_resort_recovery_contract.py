from pathlib import Path


def test_ai_recovery_bridge_is_installed_after_github_bridge():
    source = Path("app/services/__init__.py").read_text(encoding="utf-8")
    assert "install_github_access_bridge()" in source
    assert "install_ai_last_resort_recovery()" in source
    assert source.index("install_github_access_bridge()") < source.index("install_ai_last_resort_recovery()")


def test_human_escalation_only_exists_after_ai_last_resort():
    source = Path("app/services/ai_recovery_bridge.py").read_text(encoding="utf-8")
    assert "AI_ESCALATION_MARKER" in source
    assert 'category="external_dependency"' in source
    assert 'strategy="ai_last_resort_then_human"' in source
    assert "human_only_after_ai" in source
    assert 'category != "codex_auth"' in source


def test_recoverable_blocked_tasks_are_requeued_for_ai():
    source = Path("app/services/ai_recovery_bridge.py").read_text(encoding="utf-8")
    assert "TaskStatus.awaiting_approval" in source
    assert "TaskStatus.blocked" in source
    assert "TaskStatus.failed" in source
    assert "recovery.status = TaskStatus.queued" in source
    assert "recovery.requires_approval = False" in source


def test_ai_fallback_does_not_fake_success_without_checkout():
    source = Path("app/services/ai_recovery_bridge.py").read_text(encoding="utf-8")
    assert '"mode": "ai-last-resort-diagnosis"' in source
    assert '"exit_code": 78' in source
    assert "não invente sucesso" in source.lower()
