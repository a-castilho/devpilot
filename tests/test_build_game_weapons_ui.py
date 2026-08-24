from pathlib import Path


TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
BUILD_GAME_WEAPONS_JS = Path("app/static/build-game-weapons.js")


def test_build_game_loads_spaceship_weapon_telemetry():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "/assets/build-game-weapons.js?v=20260824-1" in loader
    assert "data-build-game-weapons-loader" in loader


def test_weapon_panel_maps_real_game_tasks_to_shots_and_targets():
    source = BUILD_GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "[DEVPILOT_BUILD_GAME_V1]" in source
    assert "devpilot-build-game-mission" in source
    assert "/tasks?project_id=${encodeURIComponent(projectId)}&limit=500" in source
    assert "Disparados" in source
    assert "Não disparados" in source
    assert "Acertou o alvo" in source
    assert "Errou o alvo" in source
    assert "normalize(task?.status) === 'completed'" in source
    assert "new Set(['failed', 'cancelled'])" in source
    assert "new Set(['awaiting_approval', 'queued', 'running', 'review'])" in source
    assert "normalize(task?.status) === 'blocked'" in source


def test_weapon_accuracy_only_uses_resolved_shots():
    source = BUILD_GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "const resolved = hits + misses" in source
    assert "Math.round((hits / resolved) * 100)" in source
    assert "PHASE_COUNT - attemptedPhases.size" in source
    assert "Precisão de tiro" in source
    assert "Em voo" in source
    assert "Travados" in source
