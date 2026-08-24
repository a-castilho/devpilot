from pathlib import Path


BUILD_GAME_JS = Path("app/static/build-game.js")
TASK_ANALYTICS_JS = Path("app/static/task-analytics.js")


def test_build_game_is_loaded_from_dashboard():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "/assets/build-game.js?v=20260824-1" in loader
    assert "data-build-game-loader" in loader


def test_build_game_uses_real_project_tasks_and_sequential_gates():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "[DEVPILOT_BUILD_GAME_V1]" in source
    assert "Mapa da missão" in source
    assert "Batalha de testes" in source
    assert "Chefe final" in source
    assert "normalize(task?.status) === 'completed'" in source
    assert "phase.id <= game.current" in source
    assert "/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500" in source
    assert "Conclua a fase atual antes de avançar" in source


def test_each_game_phase_creates_an_executable_devpilot_task():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "await api('/tasks'" in source
    assert "[DEVPILOT_MODE=develop]" in source
    assert "requires_approval: false" in source
    assert "source: 'dashboard'" in source
    assert "CRITÉRIO DE VITÓRIA" in source
    assert "não invente aprovação" in source
    assert "não use fallback que transforme falha em sucesso" in source


def test_game_preserves_history_and_supports_new_missions():
    source = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "devpilot-build-game-mission" in source
    assert "Começar uma nova partida? O histórico atual será preservado nas tarefas." in source
    assert ".devpilot/build-game.md" in source
    assert "XP" in source


def test_legacy_review_does_not_freeze_game_progression():
    loader = TASK_ANALYTICS_JS.read_text(encoding="utf-8")

    assert "old workers could leave successful game tasks in review forever" in loader
    assert "[DEVPILOT_BUILD_GAME_V1]" in loader
    assert "legacyReview" in loader
    assert "task?.requires_approval !== true" in loader
    assert "return {...task, status:'completed'}" in loader
