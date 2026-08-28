from pathlib import Path


TASK_ANALYTICS = Path("app/static/task-analytics.js")
FEATURE_LOADER = Path("app/static/feature-loader.js")
GAME_HTML = Path("app/static/game/index.html")
GAME_BOOTSTRAP = Path("app/static/game/game-bootstrap.js")


def test_game_extras_are_not_owned_by_dashboard_feature_loader():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    game_html = GAME_HTML.read_text(encoding="utf-8")
    bootstrap = GAME_BOOTSTRAP.read_text(encoding="utf-8")

    assert "__devpilotLoadGameExtras" not in analytics
    assert "devpilot:game-open" not in analytics
    assert "isGameIntent" not in analytics
    assert "LEGACY_GAME_EXTRAS" not in analytics
    assert "build-game-weapons.js" not in analytics

    assert "game: [" not in loader
    assert "gameAdvanced:" not in loader
    assert "window.__devpilotLoadGameAdvanced" not in loader
    assert "'game-shell.js'" not in loader
    assert "'build-game.js'" not in loader

    assert 'data-devpilot-game-standalone="1"' in game_html
    assert '/assets/build-game.js' in game_html
    assert '/assets/game/game-bootstrap.js' in game_html
    assert '/assets/feature-loader.js' not in game_html
    assert "window.loadBuildGame" in bootstrap
    assert "addPlaceholder('game', 'Modo Jogo')" in loader
    assert "window.location.assign('/game/index.html')" in loader


def test_game_placeholder_never_stays_loading_after_success_or_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    assert "function restorePlaceholder(button, original)" in loader
    assert "function restorePendingPlaceholders()" in loader
    assert "restorePlaceholder(button, original)" in loader
    assert "removePlaceholder(feature)" in loader


def test_navigation_away_cancels_stale_feature_open_intent():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    assert "let navigationEpoch = 0;" in loader
    assert "navigationEpoch += 1;" in loader
    assert "restorePendingPlaceholders();" in loader


def test_feature_script_loading_has_timeout_and_retryable_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    assert "FEATURE_SCRIPT_TIMEOUT_MS" in loader
    assert "Timeout ao carregar" in loader
    assert "script.dataset.devpilotFeatureLoadState = 'failed';" in loader
    assert "script.remove();" in loader


def test_game_does_not_start_on_authenticated_ui_ready():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    assert "devpilot:authenticated-ui-ready" not in analytics
    assert "devpilot:authenticated-ui-ready" not in loader


def test_task_analytics_does_not_repaint_hidden_view_on_every_mutation():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "document.querySelector('#tasks-view.active')" in source
    assert "if (document.querySelector('#tasks-view.active')) window.renderTaskAnalytics();" in source
