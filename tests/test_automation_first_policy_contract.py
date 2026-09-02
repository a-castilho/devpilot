import json
from pathlib import Path
from types import SimpleNamespace

from app.services.policy import evaluate_task
from app.task_run_routes import failure_details


def test_low_risk_work_is_automatic_and_high_risk_boundary_still_requires_approval():
    assert evaluate_task("corrija o layout responsivo e execute os testes", False).requires_approval is False
    assert evaluate_task("faça deploy em produção", False).requires_approval is True


def test_raw_codex_401_is_not_declared_human_intervention_before_recovery_engine_runs():
    run = SimpleNamespace(
        status="failed",
        logs=json.dumps({"stderr": "responses_websocket failed: HTTP error: 401 Unauthorized"}),
        summary="Execução falhou",
    )

    details = failure_details(run)

    assert details["category"] == "codex_auth"
    assert details["requires_authorization"] is False
    assert "tentará" in details["message"].lower()


def test_explicit_self_healing_exhaustion_can_require_human_action():
    run = SimpleNamespace(
        status="failed",
        logs=json.dumps(
            {
                "self_healing": {
                    "category": "codex_auth",
                    "message": "Alternativas automáticas esgotadas; nova autorização necessária.",
                    "requires_authorization": True,
                }
            }
        ),
        summary="Execução falhou",
    )

    details = failure_details(run)

    assert details["category"] == "codex_auth"
    assert details["requires_authorization"] is True


def test_voice_commands_and_resolicitations_use_approval_by_exception():
    api_source = Path("app/api.py").read_text(encoding="utf-8")
    run_source = Path("app/task_run_routes.py").read_text(encoding="utf-8")

    assert 'decision = evaluate_task(intent["prompt"], False)' in api_source
    assert "status=TaskStatus.awaiting_approval if decision.requires_approval else TaskStatus.queued" in api_source
    assert "decision = evaluate_task(correction_prompt, False)" in run_source
    assert '"automatic": not decision.requires_approval' in run_source
