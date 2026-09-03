from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_GAME = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
DELIVERY_GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
SYSTEM_DESIGN = (ROOT / "docs/SYSTEM_DESIGN.md").read_text(encoding="utf-8")


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


def run_contract():
    test_phase_one_requires_duplicate_preflight_and_system_design_before_implementation()
    test_phase_one_gate_requires_governance_evidence_not_only_completed_status()
    test_phase_one_contract_matches_canonical_system_design_flow()
    print("GAME_PHASE1_V89=OK")


if __name__ == "__main__":
    run_contract()
