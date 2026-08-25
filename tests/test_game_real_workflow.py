from app.main import app
from app.game_workflow_routes import _technical_phase
from app.models import Run


def test_game_workflow_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/game/missions/{task_id}" in paths
    assert "/api/game/missions/{task_id}/fire" in paths


def test_game_phase_uses_real_run_logs():
    assert _technical_phase(Run(status="success", logs='{"mode":"analysis-read-only"}')) == "scan"
    assert _technical_phase(Run(status="success", logs='{"mode":"execute"}')) == "fire"
    assert _technical_phase(Run(status="failed", logs='{"stderr":"failure"}')) == "miss"
    assert _technical_phase(Run(status="blocked", logs='{"mode":"budget-blocked"}')) == "shield"
