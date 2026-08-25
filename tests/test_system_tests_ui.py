import re
from pathlib import Path


SYSTEM_TESTS_JS = Path("app/static/system-tests.js")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
FEATURE_LOADER = Path("app/static/feature-loader.js")


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


def test_system_tests_asset_is_owned_by_explicit_tasks_bundle():
    analytics = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "/assets/system-tests.js" not in analytics
    tasks_bundle = re.search(r"tasks:\s*\[(.*?)\]", loader, re.DOTALL)
    assert tasks_bundle is not None
    assets = re.findall(r"'([^']+\.js)'", tasks_bundle.group(1))
    assert "task-analytics.js" in assets
    assert "system-tests.js" in assets
    assert "['.nav[data-view=\"tasks\"]', 'tasks']" in loader
