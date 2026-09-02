from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_planning_requires_duplicate_preflight_and_system_design():
    source = read("app/static/build-game.js")
    assert "preflight de duplicidade" in source
    assert "docs/SYSTEM_DESIGN.md" in source
    assert "System Design dispensado" in source
    assert "continue/reutilize" in source


def test_phase_one_gate_requires_planning_governance_evidence():
    source = read("app/static/game/delivery-gate.js")
    assert "preflight de duplicidade" in source
    assert "System Design" in source
    assert "fase 1" in source


def test_game_development_tool_documentation_exists():
    doc = read("docs/GAME_DEVELOPMENT_TOOL.md")
    for value in (
        "Continuidade por projeto",
        "Falhas e autocorreção",
        "Entrega final",
        "Carregamento e baixo consumo",
    ):
        assert value in doc
