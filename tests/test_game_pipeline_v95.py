from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "app/static/build-game.js"
SUBPHASES = ROOT / "app/static/build-game-subphases.js"
FINAL_SUMMARY = ROOT / "app/static/game/final-delivery-summary.js"
PROJECT_BUILDER = ROOT / "app/static/project-builder.js"
DELIVERY_UI = ROOT / "app/static/product-delivery-ui.js"
LINUX_ROUTES = ROOT / "app/linux_routes.py"
LINUX_UI = ROOT / "app/static/linux-game-access.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_game_engine_keeps_seven_stage_contract() -> None:
    source = text(ENGINE)

    assert "id: 7" in source
    assert "name: 'Entrega e revisão'" in source
    assert "FASE: ${phase.id}/${phases.length}" in source
    assert "após as sete etapas" in source


def test_corrective_subphases_follow_all_seven_stages() -> None:
    source = text(SUBPHASES)

    assert "'Entrega e revisão'" in source
    assert "FASE: ${phaseId}/7" in source
    assert "phaseId <= 7" in source
    assert "phaseId <= 6" not in source
    assert "FASE: ${phaseId}/6" not in source


def test_final_delivery_summary_includes_seventh_stage() -> None:
    source = text(FINAL_SUMMARY)

    assert "phase <= 7" in source
    assert "phase <= 6" not in source


def test_linux_bonus_uses_same_seven_stage_and_xp_contract() -> None:
    backend = text(LINUX_ROUTES)
    frontend = text(LINUX_UI)

    assert 'r"^FASE:\\s*(\\d+)/7\\s*$"' in backend
    assert "_GAME_PHASE_XP = {1: 100, 2: 220, 3: 100, 4: 160, 5: 80, 6: 100, 7: 140}" in backend
    assert "required_xp || 420" in frontend
    assert "fases 1, 2 e 3 concluídas · 420 XP" in frontend
    assert "360 XP" not in frontend


def test_new_project_is_ready_for_a_fresh_game_round() -> None:
    source = text(PROJECT_BUILDER)

    assert "const created = await request('/projects'" in source
    assert "prepareGame(created, description)" in source
    assert "localStorage.setItem(GAME_PROJECT_KEY, projectId)" in source
    assert "localStorage.setItem(GAME_DRAFT_PROJECT_KEY, projectId)" in source
    assert "localStorage.removeItem(GAME_MISSION_KEY)" in source
    assert "localStorage.setItem(GAME_DRAFT_GOAL_KEY, goal)" in source


def test_new_project_bootstraps_standard_cloud_environment() -> None:
    source = text(PROJECT_BUILDER)

    assert "const INFRASTRUCTURE_PROVIDERS = ['neon', 'render', 'vercel']" in source
    assert "auto_provision: true" in source
    assert "environment: 'homolog'" in source
    assert "providers: [...INFRASTRUCTURE_PROVIDERS]" in source
    assert "async function provisionInfrastructure(project)" in source
    assert "/delivery/auto`" in source
    assert "const infrastructure = await provisionInfrastructure(created)" in source
    assert "Provisionamento Neon + Render + Vercel iniciado automaticamente." in source


def test_project_card_exposes_public_delivery_url() -> None:
    source = text(DELIVERY_UI)

    assert "const url = String(delivery?.url || '').trim()" in source
    assert "product-delivery-public-url" in source
    assert "Abrir ambiente publicado" in source
    assert "🌐 ${esc(url)} ↗" in source
    assert "Array.from({length:7}" in source
    assert "Array.from({length:6}" not in source
