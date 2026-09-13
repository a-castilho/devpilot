from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static" / "super-admin-local-test.js"


def source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_mobile_super_admin_menu_keeps_full_width_rows():
    text = source()

    assert ".mobile-simple-list{display:grid!important" in text
    assert "grid-template-columns:38px minmax(0,1fr) 24px!important" in text
    assert "word-break:normal!important" in text
    assert "overflow-x:hidden!important" in text


def test_failed_or_blocked_execution_gets_diagnostic_repair_action():
    text = source()

    assert "FAILURE_STATUSES = new Set(['failed', 'blocked'])" in text
    assert "Diagnóstico / reparo" in text
    assert "button.dataset.taskRecovery = taskId" in text
    assert "execution-repair-diagnostic" in text
    assert "devpilot:tasks-rendered" in text
    assert "devpilot:view-changed" in text


def test_pipeline_repair_panel_and_mobile_menu_sync_are_preserved():
    text = source()

    assert "🛠 Reparo & Diagnóstico" in text
    assert 'id="pipeline-repair-run"' in text
    assert "/admin/pipeline-repair/run" in text
    assert "syncMobileMenuAfterAdminNavChange" in text
    assert "source:'super-admin-diagnostics'" in text
