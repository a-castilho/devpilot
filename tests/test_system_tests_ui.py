from pathlib import Path


SYSTEM_TESTS_JS = Path("app/static/system-tests.js")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")


def test_system_tests_workspace_supports_project_scoped_actions():
    source = SYSTEM_TESTS_JS.read_text(encoding="utf-8")

    assert "Testes de sistemas" in source
    assert 'data-system-tests-action="run"' in source
    assert 'data-system-tests-action="create"' in source
    assert 'data-system-tests-action="recreate"' in source
    assert "/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500" in source
    assert "devpilot-system-tests-project" in source


def test_system_test_generation_preserves_manual_tests_and_approval():
    source = SYSTEM_TESTS_JS.read_text(encoding="utf-8")

    assert "requiresApproval: true" in source
    assert ".devpilot/system-tests-manifest.json" in source
    assert "Preserve testes manuais" in source
    assert "não os apague" in source
    assert "/tasks/${button.dataset.taskId}/approve" in source


def test_system_test_run_mode_is_non_destructive():
    source = SYSTEM_TESTS_JS.read_text(encoding="utf-8")

    assert "requiresApproval: false" in source
    assert "Não modifique arquivos, código de produção, banco persistente ou infraestrutura." in source
    assert "não invente resultado" in source


def test_system_tests_asset_is_loaded():
    source = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "/assets/system-tests.js?v=20260824-1" in source
