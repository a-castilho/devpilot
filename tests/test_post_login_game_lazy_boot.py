import re
from pathlib import Path


TASK_ANALYTICS = Path("app/static/task-analytics.js")
FEATURE_LOADER = Path("app/static/feature-loader.js")
STATIC = Path("app/static")


def test_game_extras_are_owned_only_by_explicit_feature_loader():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    # O analytics deve permanecer estritamente analítico. Nenhum loader de jogo
    # pode voltar para este arquivo, evitando dupla carga e corrida no pós-login.
    assert "__devpilotLoadGameExtras" not in analytics
    assert "devpilot:game-open" not in analytics
    assert "isGameIntent" not in analytics
    assert "LEGACY_GAME_EXTRAS" not in analytics
    assert "build-game-weapons.js" not in analytics

    # O único dono do carregamento do jogo é o feature loader explícito.
    assert "FEATURE_BUNDLES" in loader
    game_bundle = re.search(r"game:\s*\[(.*?)\]", loader, re.DOTALL)
    assert game_bundle is not None
    assets = re.findall(r"'([^']+\.js)'", game_bundle.group(1))
    assert assets == [
        "build-game.js",
        "build-game-subphases.js",
        "build-game-new-session.js",
        "build-game-url-bonus.js",
        "build-game-weapons.js",
    ]
    for asset in assets:
        assert (STATIC / asset).is_file(), f"bundle do jogo referencia asset inexistente: {asset}"

    assert "addPlaceholder('game', 'Modo Jogo')" in loader
    assert "loadFeature(feature)" in loader
    assert "document.addEventListener('click'" in loader


def test_game_placeholder_never_stays_loading_after_success_or_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "function restorePlaceholder(button, original)" in loader
    assert "function restorePendingPlaceholders()" in loader
    assert "restorePlaceholder(button, original);" in loader
    assert "removePlaceholder(feature);" in loader
    assert "if (!ok) {" in loader
    assert "Tente novamente." in loader


def test_navigation_away_cancels_stale_game_open_intent():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "let navigationEpoch = 0;" in loader
    assert "const intentEpoch = navigationEpoch;" in loader
    assert "navigationEpoch += 1;" in loader
    assert "restorePendingPlaceholders();" in loader
    assert "if (intentEpoch !== navigationEpoch)" in loader
    assert "finishStalePlaceholderIntent(button, feature, ok, original);" in loader
    assert "if (intentEpoch !== navigationEpoch || !trigger.isConnected) return;" in loader


def test_feature_script_loading_has_timeout_and_retryable_failure():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "FEATURE_SCRIPT_TIMEOUT_MS" in loader
    assert "Timeout ao carregar" in loader
    assert "script.dataset.devpilotFeatureLoadState = 'failed';" in loader
    assert "script.remove();" in loader


def test_feature_loader_does_not_replay_partial_features():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    partial_guard = loader.index("if (!ok) {", loader.index("void loadFeature(feature).then"))
    replay = loader.index("trigger.dataset.devpilotFeatureReplay = '1';", partial_guard)
    guard_return = loader.index("return;", partial_guard)
    assert guard_return < replay


def test_game_does_not_start_on_authenticated_ui_ready():
    analytics = TASK_ANALYTICS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "devpilot:authenticated-ui-ready" not in analytics
    assert "devpilot:authenticated-ui-ready" not in loader


def test_task_analytics_does_not_repaint_hidden_view_on_every_mutation():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "document.querySelector('#tasks-view.active')" in source
    assert "if (document.querySelector('#tasks-view.active')) window.renderTaskAnalytics();" in source
