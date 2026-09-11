from pathlib import Path


def test_empty_repository_bootstrap_runtime_is_loaded():
    init_source = Path("app/__init__.py").read_text(encoding="utf-8")
    assert "empty_repository_bootstrap" in init_source


def test_empty_repository_is_not_a_human_approval_blocker():
    source = Path("app/empty_repository_bootstrap.py").read_text(encoding="utf-8")
    assert "This is NOT a blocker and does NOT require user approval" in source
    assert "empty_repository_bootstrap" in source
    assert "analysis-read-only-empty-repository" in source
    assert "_execute_empty_repository" in source
    assert "alternating_flow._execute_action = execute_action" in source


def test_autonomous_build_report_forbids_reasking_permission():
    source = Path("app/empty_repository_bootstrap.py").read_text(encoding="utf-8")
    assert "AUTONOMOUS BUILD CONTRACT" in source
    assert "Do not ask the client to authorize normal development work" in source
    assert "A missing implementation is work to perform, not a reason to stop" in source


def test_empty_repository_bootstrap_requires_deployable_basics():
    source = Path("app/empty_repository_bootstrap.py").read_text(encoding="utf-8")
    assert "tests, README/run instructions and a Dockerfile" in source
    assert "implement the requested feature completely" in source.lower()
