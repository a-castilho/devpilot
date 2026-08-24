from pathlib import Path


GAME_WEAPONS_JS = Path("app/static/game-weapons.js")
TASK_MODAL_JS = Path("app/static/task-modal.js")


def test_game_weapons_is_loaded_by_task_modal():
    loader = TASK_MODAL_JS.read_text(encoding="utf-8")

    assert "/assets/game-weapons.js?v=20260824-1" in loader
    assert "data-game-weapons-loader" in loader
    assert "gameWeaponsLoader" in loader


def test_new_task_becomes_weapon_development_only_in_game_mode():
    source = GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "#build-game-view.active" in source
    assert "⚔ Desenvolver armas" in source
    assert "ARSENAL DA NAVE" in source
    assert "Desenvolver armas" in source
    assert "Tipo de arma" in source
    assert "Nome da arma" in source
    assert "Alvo / contexto" in source
    assert "Desenvolver arma" in source


def test_each_devpilot_mode_uses_the_same_weapon_names_as_the_workshop():
    source = GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "📡 Radar de análise · analisar / diagnosticar" in source
    assert "⚡ Laser construtor · desenvolver / implementar" in source
    assert "🎯 Canhão de correção · corrigir / depurar" in source
    assert "📡 Radar de análise · revisar / validar" in source
    assert "segurança, testes, deploy e Linux" in source


def test_normal_task_vocabulary_is_restored_outside_game_mode():
    source = GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "NOVA TAREFA" in source
    assert "Analisar / diagnosticar" in source
    assert "Desenvolver / implementar" in source
    assert "parts.mode.dispatchEvent(new Event('change'" in source


def test_game_weapon_ui_tracks_navigation_and_dynamic_game_view():
    source = GAME_WEAPONS_JS.read_text(encoding="utf-8")

    assert "MutationObserver" in source
    assert "attributeFilter: ['class', 'open']" in source
    assert "[data-project-build-game]" in source
