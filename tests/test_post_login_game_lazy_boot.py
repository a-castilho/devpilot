import re
from pathlib import Path


TASK_ANALYTICS = Path("app/static/task-analytics.js")
FEATURE_LOADER = Path("app/static/feature-loader.js")
STATIC = Path("app/static")


def test_game_extras_are_owned_only_by_explicit_feature_loader():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "__devpilotLoadGameExtras" not in analytics
    assert "devpilot:game-open" not in analytics
    assert "isGameIntent" not in analytics
    assert "LEGACY_GAME_EXTRAS" not in analytics
    assert "build-game-weapons.js" not in analytics

    assert "FEATURE_BUNDLES" in loader
    game_bundle = re.search(r"game:\s*\[(.*?)\]", loader, re.DOTALL)
    assert game_bundle is not None
    assets = re.findall(r"'([^']+\.js)'", game_bundle.group(1))
    required = {
        "build-game.js",
        "build-game-subphases.js",
        "build-game-new-session.js",
        "build-game-url-bonus.js",
        "build-game-weapons.js",
    }
    assert required.issubset(set(assets))
    for asset in assets:
        assert (STATIC / asset).is_file(), f"bundle do jogo referencia asset inexistente: {asset}"

    assert "addPlaceholder('game', 'Modo Jogo')" in loader
    assert "loadFeature(feature)" in loader
    assert "document.addEventListener('click'" in loader


def test_game_does_not_start_on_authenticated_ui_ready():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "devpilot:authenticated-ui-ready" not in analytics
    assert "devpilot:authenticated-ui-ready" not in loader


def test_task_analytics_does_not_repaint_hidden_view_on_every_mutation():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "document.querySelector('#tasks-view.active')" in source
    assert "if (document.querySelector('#tasks-view.active')) window.renderTaskAnalytics();" in source
