from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "app/static/game/stable-round-ui.js"
RECOVERY = ROOT / "app/static/game/recovery-runtime.js"
RECOVERY_SERVICE = ROOT / "app/services/failure_recovery.py"
RECOVERY_ROUTES = ROOT / "app/failure_recovery_routes.py"
KEEPER = ROOT / "app/static/game/flow-keeper.js"
RUNTIME_SYNC = ROOT / "app/static/game/runtime-state-sync.js"
BOOT = ROOT / "app/static/game/game-bootstrap.js"
INDEX = ROOT / "app/static/game/index.html"


def test_active_round_surface_lives_outside_polling_target():
    source = STABLE.read_text(encoding="utf-8")
    assert "devpilot-game-stable-round-v97" in source
    assert "document.querySelector('.devpilot-game-stage')" in source
    assert "target.style.setProperty('display', detailsOpen ? 'block' : 'none', 'important')" in source
    assert "if (nextSignature === lastSignature) return true" in source


def test_failure_surface_reports_real_reason_and_proposed_fix_before_retry():
    source = STABLE.read_text(encoding="utf-8")
    assert "Diagnóstico da falha" in source
    assert "failure?.technical_message" in source
    assert "failure?.recommended_action" in source
    assert "Correção proposta" in source
    assert "data-game-recovery-correction" in source
    assert "Falha diagnosticada. Confira o motivo e a correção proposta" in source
    assert "↻ Corrigir e continuar" in source
    assert "Aplicando a correção proposta…" in source


def test_safe_recovery_is_staged_until_user_clicks_fix_and_continue():
    service = RECOVERY_SERVICE.read_text(encoding="utf-8")
    routes = RECOVERY_ROUTES.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")
    keeper = KEEPER.read_text(encoding="utf-8")

    assert "def enrich_failure_from_run" in service
    assert 'status=TaskStatus.awaiting_approval' in service
    assert 'if actor == "owner" and _activate_automatic_recovery' in service
    assert 'action="failure_recovery.prepared"' in service
    assert 'action="failure_recovery.user_started"' in service
    assert "CORREÇÃO PROPOSTA" in service
    assert "recommended_action" in service

    assert 'return "awaiting_intervention" if recovery.requires_approval else "ready_to_recover"' in routes
    assert "enrich_failure_from_run(original_run, failure_details(original_run))" in routes

    assert "__devpilotGameReadRecovery" in recovery
    assert "readCanonicalRecovery(key, {escalate: false})" in recovery
    assert "readCanonicalRecovery(taskId, {escalate: true})" in recovery
    assert "request(taskId, 'escalate')" in recovery

    failed_observer = keeper.split("const existingRecovery = recoveryFor(state);", 1)[1]
    assert "await window.__devpilotGameReadRecovery?.(state.taskId)" in failed_observer
    assert "await engine.retry()" not in failed_observer
    assert "O único gatilho de correção é o clique" in keeper


def test_internal_recovery_task_never_becomes_game_phase():
    source = RUNTIME_SYNC.read_text(encoding="utf-8")
    assert "[DEVPILOT_FAILURE_RECOVERY_V1]" in source
    assert "failure-recovery" in source
    assert ".filter(task => !isFailureRecoveryTask(task))" in source


def test_bootstrap_forces_v97_assets_after_recovery_ui_change():
    boot = BOOT.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    assert "game/stable-round-ui.js" in boot
    assert "game-flow-v97-20260904" in boot
    assert "game-flow-v97-20260904" in html
    assert "unified-v97" in boot
    assert 'data-devpilot-game-version="v97"' in html


def run_contract():
    test_active_round_surface_lives_outside_polling_target()
    test_failure_surface_reports_real_reason_and_proposed_fix_before_retry()
    test_safe_recovery_is_staged_until_user_clicks_fix_and_continue()
    test_internal_recovery_task_never_becomes_game_phase()
    test_bootstrap_forces_v97_assets_after_recovery_ui_change()
    print("GAME_STABLE_ROUND_UI_V97=OK")


if __name__ == "__main__":
    run_contract()
