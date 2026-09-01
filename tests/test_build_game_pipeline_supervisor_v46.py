from pathlib import Path

from app.services.policy import evaluate_task


ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app/static/game/index.html"
SUPERVISOR = ROOT / "app/static/game/pipeline-supervisor.js"
STALE_APPROVAL = ROOT / "app/static/game/stale-approval-reconciler.js"
DELIVERY_GATE = ROOT / "app/static/game/delivery-gate.js"
BUILD_GAME = ROOT / "app/static/build-game.js"


def test_game_pipeline_supervisor_loads_after_delivery_gate_before_bootstrap():
    html = GAME_HTML.read_text(encoding="utf-8")

    gate = html.index("/assets/game/delivery-gate.js")
    supervisor = html.index("/assets/game/pipeline-supervisor.js")
    stale = html.index("/assets/game/stale-approval-reconciler.js")
    bootstrap = html.index("/assets/game/game-bootstrap.js")

    assert gate < supervisor < stale < bootstrap


def test_game_safety_guardrails_do_not_create_false_approval_gate():
    prompt = """
    Implemente a menor fatia funcional.
    Esta fase NÃO pode terminar apenas com análise, relatório, URL, deploy já existente ou validação do estado atual.
    Use Git de forma reversível e nunca force push na branch principal.
    Quando houver deploy configurado e autorizado, confirme healthcheck e smoke do ambiente já existente.
    Revise dependências sem alterar pacotes.
    """

    decision = evaluate_task(prompt)

    assert decision.requires_approval is False
    assert decision.reasons == ()


def test_real_high_risk_actions_still_require_approval():
    cases = {
        "Faça git push origin main.": "push",
        "Faça deploy em produção agora.": "deploy",
        "Atualize as dependências do projeto.": "dependency",
        "Execute rm -rf na pasta de dados.": "destructive",
    }

    for prompt, expected in cases.items():
        decision = evaluate_task(prompt)
        assert decision.requires_approval is True, prompt
        assert expected in decision.reasons, prompt


def test_stale_game_approval_is_reconciled_only_when_current_policy_has_no_risk_reason():
    script = STALE_APPROVAL.read_text(encoding="utf-8")

    assert "/orchestrator" in script
    assert "if (reasons.length) return false" in script
    assert "generatedByGame(task)" in script
    assert "/approve" in script
    assert "/next" in script
    assert "gate legado sem risco real" in script


def test_supervisor_keeps_real_approval_gate_visible():
    script = SUPERVISOR.read_text(encoding="utf-8")

    assert "Gate de autorização real" in script
    assert "O jogo não vai contornar esse limite" in script
    assert "data-pipeline-approve" in script
    assert "/approve" in script


def test_supervisor_uses_recovery_instead_of_duplicate_failed_phase():
    script = SUPERVISOR.read_text(encoding="utf-8")

    assert "/recovery" in script
    assert "/recovery/escalate" in script
    assert "/recovery/intervene" in script
    assert "/recovery/resume" in script
    assert "Falha não vira nova jogada duplicada" in script
    assert "Retestar fase original" in script


def test_supervisor_refreshes_live_pipeline_until_delivery_gate_is_created():
    script = SUPERVISOR.read_text(encoding="utf-8")
    delivery = DELIVERY_GATE.read_text(encoding="utf-8")

    assert "const LIVE = new Set(['queued', 'planning', 'running', 'review'])" in script
    assert "scheduleRefresh(3500)" in script
    assert "window.loadBuildGame" in script
    assert "window.__devpilotEnsureDeliveryGate" in delivery
    assert "[DEVPILOT_DELIVERY_VERIFIER_V1]" in delivery


def test_build_game_still_requires_completed_latest_task_for_phase_progression():
    script = BUILD_GAME.read_text(encoding="utf-8")

    assert "const isPassed = task => normalize(task?.status) === 'completed';" in script
    assert "const current = phases.find(phase => !isPassed(byPhase.get(phase.id)))" in script
