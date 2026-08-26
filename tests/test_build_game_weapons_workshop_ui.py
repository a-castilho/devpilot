from pathlib import Path


TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")
FEATURE_LOADER_JS = Path("app/static/feature-loader.js")
WEAPONS_JS = Path("app/static/build-game-weapons.js")


def test_weapons_workshop_is_loaded_only_by_explicit_advanced_game_bundle():
    analytics = TASK_ANALYTICS_JS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")

    assert "build-game-weapons.js" not in analytics
    assert "game: ['game-shell.js', 'build-game.js']" in loader
    assert "gameAdvanced:" in loader
    advanced_block = loader.split("gameAdvanced:", 1)[1].split("],", 1)[0]
    assert "'build-game-weapons.js'" in advanced_block
    assert "window.__devpilotLoadGameAdvanced = () => loadFeature('gameAdvanced')" in loader
    assert "addPlaceholder('game', 'Modo Jogo')" in loader


def test_ship_cards_and_cockpit_have_weapons_entry_points():
    source = WEAPONS_JS.read_text(encoding="utf-8")
    assert "data-project-weapons" in source
    assert "data-cockpit-weapons" in source
    assert "⚔ Armas" in source
    assert "Abrir desenvolvimento das armas da nave" in source


def test_every_real_action_is_classified_as_a_weapon_type():
    source = WEAPONS_JS.read_text(encoding="utf-8")
    for key in (
        "analysis",
        "correction",
        "development",
        "testing",
        "security",
        "deploy",
        "infrastructure",
        "execution",
    ):
        assert f"key:'{key}'" in source
    assert "function classifyTask(task)" in source
    assert "WEAPON_BY_KEY[classifyTask(task)]" in source


def test_weapons_use_real_project_tasks_and_real_outcomes():
    source = WEAPONS_JS.read_text(encoding="utf-8")
    assert "/tasks?project_id=${encodeURIComponent(projectId)}&limit=500" in source
    assert "normalize(task?.status) === 'completed'" in source
    assert "MISS_STATUSES" in source
    assert "ACTIVE_STATUSES" in source
    assert "normalize(task?.status) === 'blocked'" in source
    assert "sem inventar resultados" in source


def test_workshop_exposes_weapon_development_telemetry():
    source = WEAPONS_JS.read_text(encoding="utf-8")
    assert "OFICINA DE ARMAS · DESENVOLVIMENTO" in source
    assert "Maturidade por uso real" in source
    assert "Últimos disparos · ação → arma" in source
    assert "Disparos" in source
    assert "Acertos" in source
    assert "Precisão resolvida" in source
