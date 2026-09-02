from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTINUITY = (ROOT / "app/static/game/development-continuity.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "app/static/game/runtime.js").read_text(encoding="utf-8")
ROUTES = (ROOT / "app/frontend_ui_routes.py").read_text(encoding="utf-8")
SUMMARY = (ROOT / "app/static/game/final-delivery-summary.js").read_text(encoding="utf-8")
BONUS = (ROOT / "app/static/build-game-url-bonus.js").read_text(encoding="utf-8")
DELIVERY_UI = (ROOT / "app/static/product-delivery-ui.js").read_text(encoding="utf-8")


def test_game_can_switch_projects_and_resume_existing_work():
    assert "switchProject(projectId)" in CONTINUITY
    assert "localStorage.removeItem(MISSION_KEY)" in CONTINUITY
    assert "repairStaleMission(state)" in CONTINUITY
    assert "devpilot:game:projects-ready" in CONTINUITY
    assert "data-game80-project-switch" in CONTINUITY


def test_game_loads_all_projects_in_bounded_pages():
    assert "offset: int = Query(0" in ROUTES
    assert ".offset(offset)" in ROUTES
    assert "PAGE_SIZE = 100" in CONTINUITY
    assert "MAX_PROJECTS = 1000" in CONTINUITY
    assert "/ui/projects?limit=${PAGE_SIZE}&offset=${offset}" in CONTINUITY


def test_game_recovers_failed_or_blocked_execution_before_asking_user():
    assert "/recovery/escalate" in CONTINUITY
    assert "/recovery/resume" in CONTINUITY
    assert "/recovery/intervene" in CONTINUITY
    assert "['failed', 'blocked', 'cancelled', 'canceled']" in CONTINUITY
    assert "manual_intervention_required" in CONTINUITY
    assert "Orientar agente e continuar" in CONTINUITY


def test_compact_runtime_keeps_enough_history_after_retries():
    assert "/ui/projects?limit=100" in RUNTIME
    assert "limit=80" in RUNTIME
    assert "limit: int = Query(80, ge=1, le=100)" in ROUTES


def test_delivery_is_compatible_with_web_service_cli_and_automation_projects():
    assert "_project_delivery_mode" in ROUTES
    assert 'return "web"' in ROUTES
    assert 'return "service"' in ROUTES
    assert 'return "code"' in ROUTES
    assert "requiresPublicUrl" in BONUS
    assert "deliveryMode() === 'web'" in BONUS
    assert "Este projeto não exige URL pública para concluir a rodada." in BONUS


def test_all_seven_phases_are_reported():
    assert "phase <= 7" in SUMMARY
    assert "startsWith('[Jogo] Gate')" in SUMMARY
    assert "Array.from({length:7}" in DELIVERY_UI


def test_v80_is_loaded_after_simple_ui_and_knows_current_user():
    assert "'game/development-continuity.js'" in BOOT
    assert BOOT.index("'game/objective-controls.js'") < BOOT.index("'game/development-continuity.js'")
    assert "window.api('/auth/me')" in BOOT
    assert "game-development-v80-20260902" in BOOT



def test_delivery_mode_classifier_is_functional():
    import json
    from app.frontend_ui_routes import _project_delivery_mode

    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["saas"], "frontend": ["react"]}})) == "web"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["api"], "frontend": ["none"]}})) == "service"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["cli"], "frontend": ["none"]}})) == "code"
    assert _project_delivery_mode(json.dumps({"project_blueprint": {"project_type": ["automation"], "frontend": ["none"]}})) == "code"


def test_v80_keeps_visible_fallback_and_sequential_dedup_guards():
    index = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
    guard = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
    assert "data-game-critical-boot-v80" in index
    assert "Preparando Modo Jogo" in index
    assert "window.__devpilotGameCreateSequentialDedup = true" in guard
    assert "recentCreations" in guard
    assert "action-runtime.js" not in BOOT.split("const ENTRY_ASSETS = [", 1)[1].split("];", 1)[0]


def test_explicit_new_round_suppresses_history_resume_until_start():
    assert "function hasNewRoundIntent()" in CONTINUITY
    assert "sessionStorage.setItem(NEW_ROUND_INTENT_KEY, '1')" in CONTINUITY
    assert "if (hasNewRoundIntent()) return" in CONTINUITY
    assert "if (state?.hasTasks) sessionStorage.removeItem(NEW_ROUND_INTENT_KEY)" in CONTINUITY
