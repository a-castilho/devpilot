from pathlib import Path
from types import SimpleNamespace

from app.services.failure_recovery import RECOVERY_MARKER, recovery_prompt


ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / "app/failure_recovery_routes.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "app/services/failure_recovery.py").read_text(encoding="utf-8")
UI = (ROOT / "app/static/task-recovery-flow.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_recovery_prompt_requires_root_cause_and_proof_before_original_retry():
    task = SimpleNamespace(
        id="task-original",
        title="Criar login por perfil",
        prompt="Implementar login, senha e autorização por perfil.",
    )
    run = SimpleNamespace(id="run-failed")
    prompt = recovery_prompt(
        task,
        run,
        {
            "category": "unknown",
            "code": "EXECUTION_FAILED",
            "message": "test suite failed",
            "requires_authorization": False,
        },
    )

    assert RECOVERY_MARKER in prompt
    assert "[failure-origin-task:task-original]" in prompt
    assert "causa raiz" in prompt.lower()
    assert "não repetir cegamente" in prompt.lower()
    assert "execute testes relevantes" in prompt.lower()
    assert "recolocará automaticamente a execução original" in prompt


def test_backend_exposes_full_recovery_state_machine_without_schema_migration():
    assert '@router.get("/tasks/{task_id}/recovery")' in ROUTES
    assert '@router.post("/tasks/{task_id}/recovery/escalate")' in ROUTES
    assert '@router.post("/tasks/{task_id}/recovery/intervene")' in ROUTES
    assert '@router.post("/tasks/{task_id}/recovery/resume")' in ROUTES
    for state in (
        "ready_to_recover",
        "agent_recovery",
        "awaiting_intervention",
        "intervention_required",
        "recovery_exhausted",
        "retesting",
        "resolved",
    ):
        assert state in ROUTES
    assert "class FailureRecovery" not in SERVICE
    assert "mapped_column" not in SERVICE


def test_agent_recovery_is_idempotent_and_never_recursively_spawns_itself():
    assert 'Task.source == "failure-recovery"' in SERVICE
    assert "if is_failure_recovery_task(original_task):" in SERVICE
    assert "find_failure_recovery_task(db, original_task)" in SERVICE
    assert "if existing:" in SERVICE
    assert "return existing" in SERVICE


def test_human_guidance_requeues_same_recovery_task_instead_of_duplicating_it():
    assert "INTERVENÇÃO ASSISTIDA DO USUÁRIO" in SERVICE
    assert "recovery.status = TaskStatus.queued" in SERVICE
    assert "failure_recovery.user_guidance" in SERVICE
    assert "Task(" not in ROUTES.split("def intervene_recovery", 1)[1]


def test_execution_ui_loads_recovery_flow_and_displays_three_levels():
    assert "'task-recovery-flow.js'" in LOADER
    assert "⚡ Recuperar" not in UI  # icon comes from CSS; label stays accessible text
    assert "button.textContent = 'Recuperar'" in UI
    assert "NÍVEL 1" in UI
    assert "NÍVEL 2" in UI
    assert "NÍVEL 3" in UI
    assert "Autocorreção" in UI
    assert "Agente de recuperação" in UI
    assert "INTERVENÇÃO ASSISTIDA" in UI
    assert "Retestar execução original" in UI


def test_recovery_router_is_registered_in_application():
    assert "from app.failure_recovery_routes import router as failure_recovery_router" in MAIN
    assert "app.include_router(failure_recovery_router)" in MAIN
