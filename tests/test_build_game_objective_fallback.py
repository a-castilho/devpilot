from pathlib import Path


BUILD_GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")


def test_blank_game_objective_is_filled_before_play_handler_runs():
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "function ensurePlayableGoal(button)" in source
    assert "#build-game-view [data-play-phase]" in source
    assert "document.addEventListener('click'" in source
    assert "}, true);" in source
    assert "if (!view || !input || String(input.value || '').trim()) return false;" in source
    assert "input.value = automaticGoal(view)" in source
    assert "input.dispatchEvent(new Event('input', {bubbles: true}))" in source


def test_automatic_game_goal_uses_project_context_without_fake_success():
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "const description = String(project?.description || '').trim();" in source
    assert "if (description) return description;" in source
    assert "const projectName = String(project?.name || selectedName || scoreName || 'selecionado').trim();" in source
    assert "Evoluir o projeto ${projectName} com uma entrega funcional, testada e verificável." in source
    assert "input.value = automaticGoal(view)" in source
    assert "Objetivo definido automaticamente. Iniciando a fase…" in source
