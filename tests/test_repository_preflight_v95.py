from pathlib import Path

from app.services.recovery import AutoRecoveryService


ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "app/services/alternating_flow.py").read_text(encoding="utf-8")


def test_missing_repository_is_classified_deterministically() -> None:
    recovery = AutoRecoveryService()

    assert recovery.classify('fatal: repository "" does not exist') == "repository_not_ready"
    assert recovery.classify("REPOSITORY_NOT_READY: repository_url is empty") == "repository_not_ready"


def test_repository_preflight_runs_before_any_task_mode() -> None:
    assert "def _ensure_project_repository(project: Project) -> bool:" in FLOW
    assert "provision_repository_in_background(" in FLOW
    assert "if not _ensure_project_repository(project):" in FLOW
    assert "return _repository_not_ready_result()" in FLOW

    execute_body = FLOW.split("def execute_task(project: Project, task: Task) -> dict:", 1)[1]
    preflight = execute_body.index("if not _ensure_project_repository(project):")
    verification = execute_body.index("if is_verification_analysis(task):")
    action = execute_body.index("if is_analysis_action_task(task):")
    default = execute_body.index("return executor_service.execute_task(project, task)")
    assert preflight < verification < action < default


def test_repository_preflight_never_invokes_git_with_empty_url() -> None:
    assert '"mode": "repository-preflight"' in FLOW
    assert '"exit_code": 78' in FLOW
    assert '"category": "repository_not_ready"' in FLOW
    assert 'f"{REPOSITORY_NOT_READY}: repository_url is empty"' in FLOW
    assert "Nenhum comando Git, Codex ou alteração de código foi executado" in FLOW
