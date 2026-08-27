import re
from pathlib import Path


TASK_ANALYTICS = Path("app/static/task-analytics.js")
FEATURE_LOADER = Path("app/static/feature-loader.js")
STATIC = Path("app/static")


def _bundle_assets(source: str, name: str) -> list[str]:
    match = re.search(rf"{re.escape(name)}:\s*\[(.*?)\]", source, re.DOTALL)
    assert match is not None, f"bundle {name} ausente"
    return re.findall(r"'([^']+\.js)'", match.group(1))


def test_game_extras_are_owned_only_by_explicit_feature_loader():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    # Analytics permanece estritamente analítico: nenhum segundo loader do jogo.
    assert "__devpilotLoadGameExtras" not in analytics
    assert "devpilot:game-open" not in analytics
    assert "isGameIntent" not in analytics
    assert "LEGACY_GAME_EXTRAS" not in analytics
    assert "build-game-weapons.js" not in analytics

    # Entrada do jogo é deliberadamente mínima para proteger a thread principal.
    base_assets = _bundle_assets(loader, "game")
    assert base_assets == ["game-shell.js", "build-game.js"]

    # Recursos pesados permanecem disponíveis, mas em um segundo bundle explícito.
    advanced_assets = _bundle_assets(loader, "gameAdvanced")
    required_advanced = {
        "build-game-subphases.js",
        "build-game-repair-mission.js",
        "build-game-new-session.js",
        "build-game-url-bonus.js",
        "build-game-weapons.js",
    }
    assert required_advanced.issubset(set(advanced_assets))
    assert "window.__devpilotLoadGameAdvanced = () => loadFeature('gameAdvanced');" in loader

    for asset in [*base_assets, *advanced_assets]:
        assert (STATIC / asset).is_file(), f"bundle do jogo referencia asset inexistente: {asset}"

    assert "addPlaceholder('game', 'Modo Jogo')" in loader
    assert "loadFeature(feature)" in loader
    assert "document.addEventListener('click'" in loader


def test_game_placeholder_never_stays_loading_after_success_or_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "function restorePlaceholder(button, original)" in loader
    assert "function restorePendingPlaceholders()" in loader
    assert "restorePlaceholder(button, original)" in loader
    assert "removePlaceholder(feature)" in loader
    assert "if (!ok) {" in loader
    assert "Tente novamente." in loader


def test_navigation_away_cancels_stale_game_open_intent():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "let navigationEpoch = 0;" in loader
    assert "const intentEpoch = navigationEpoch;" in loader
    assert "navigationEpoch += 1;" in loader
    assert "restorePendingPlaceholders();" in loader
    assert "if (intentEpoch !== navigationEpoch) return restorePlaceholder(button, original);" in loader
    assert "if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;" in loader


def test_feature_script_loading_has_timeout_and_retryable_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "FEATURE_SCRIPT_TIMEOUT_MS" in loader
    assert "Timeout ao carregar" in loader
    assert "script.dataset.devpilotFeatureLoadState = 'failed';" in loader
    assert "script.remove();" in loader


def test_feature_loader_does_not_replay_partial_features():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    then_block = loader.split("void loadFeature(feature).then(ok => {", 1)[1]
    assert "if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;" in then_block
    assert then_block.index("if (!ok || intentEpoch !== navigationEpoch || !trigger.isConnected) return;") < then_block.index("trigger.dataset.devpilotFeatureReplay = '1';")


def test_game_does_not_start_on_authenticated_ui_ready():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "devpilot:authenticated-ui-ready" not in analytics
    assert "devpilot:authenticated-ui-ready" not in loader


def test_task_analytics_does_not_repaint_hidden_view_on_every_mutation():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "document.querySelector('#tasks-view.active')" in source
    assert "if (document.querySelector('#tasks-view.active')) window.renderTaskAnalytics();" in source
