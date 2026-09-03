import re
from pathlib import Path

from app.services.policy import evaluate_task


ROOT = Path(__file__).resolve().parents[1]
BUILD_GAME = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
DELIVERY_GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
SYSTEM_DESIGN = (ROOT / "docs/SYSTEM_DESIGN.md").read_text(encoding="utf-8")


def phase_one_mission() -> str:
    match = re.search(
        r"id:\s*1,.*?mission:\s*`(?P<mission>.*?)`\s*\n\s*},\s*\n\s*{\s*\n\s*id:\s*2,",
        BUILD_GAME,
        re.DOTALL,
    )
    assert match, "missão da fase 1 não encontrada"
    return match.group("mission")


def test_phase_one_requires_duplicate_preflight_and_system_design_before_implementation():
    assert "preflight de duplicidade" in BUILD_GAME
    assert "docs/SYSTEM_DESIGN.md" in BUILD_GAME
    assert 'System Design dispensado' in BUILD_GAME
    assert "continue/reutilize" in BUILD_GAME
    assert "Não implemente a funcionalidade nesta etapa" in BUILD_GAME


def test_phase_one_gate_requires_governance_evidence_not_only_completed_status():
    assert "Para a fase 1" in DELIVERY_GATE
    assert "preflight de duplicidade" in DELIVERY_GATE
    assert "System Design" in DELIVERY_GATE
    assert "não aprove o Planejamento" in DELIVERY_GATE


def test_phase_one_contract_matches_canonical_system_design_flow():
    assert "Demanda → preflight de duplicidade → System Design → implementação" in SYSTEM_DESIGN
    assert "Nenhuma edição deve começar antes" in SYSTEM_DESIGN


def test_phase_one_internal_planning_text_does_not_force_high_risk_approval():
    mission = phase_one_mission()
    decision = evaluate_task(mission, requested_approval=False)

    assert decision.requires_approval is False, decision.reasons
    assert decision.reasons == ()
    assert "topologia de entrega" in mission


def run_contract():
    test_phase_one_requires_duplicate_preflight_and_system_design_before_implementation()
    test_phase_one_gate_requires_governance_evidence_not_only_completed_status()
    test_phase_one_contract_matches_canonical_system_design_flow()
    test_phase_one_internal_planning_text_does_not_force_high_risk_approval()
    print("GAME_PHASE1_V89=OK")


if __name__ == "__main__":
    run_contract()
