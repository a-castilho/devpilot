from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/execution-ship-v45.css").read_text(encoding="utf-8")


def test_execution_ship_stylesheet_is_loaded_after_game_operations():
    assert "devpilot-game-operations-v39" in NAV
    assert "devpilot-execution-ship-v45" in NAV
    assert "/assets/execution-ship-v45.css?v=20260901-1" in NAV
    assert NAV.index("devpilot-game-operations-v39") < NAV.index("devpilot-execution-ship-v45")


def test_execution_card_has_ship_sections_and_status_hull():
    for token in (
        'content:"COCKPIT"',
        'content:"ESTADO DA NAVE"',
        'content:"COMANDOS"',
        '.tasks-v9-row:has(.tasks-v9-status.failed)::before',
        '.tasks-v9-row:has(.tasks-v9-status.completed)::before',
    ):
        assert token in CSS


def test_open_details_are_visually_attached_to_the_mission_ship():
    assert '.tasks-v9-row:has(+ .task-details-row:not([hidden]))' in CSS
    assert 'content:"LOG DA MISSÃO · TELEMETRIA"' in CSS
    assert 'border-radius:0 0 18px 18px' in CSS


def test_mobile_keeps_two_command_columns_and_wraps_long_actions():
    assert '@media (max-width:520px)' in CSS
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in CSS
    assert 'white-space:normal' in CSS
    assert 'overflow-wrap:anywhere' in CSS
