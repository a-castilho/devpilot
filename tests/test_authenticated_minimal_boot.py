from pathlib import Path

from app.main import _CORE_AUTHENTICATED_SCRIPTS, _DEFERRED_AUTHENTICATED_SCRIPTS


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "app/static/acs-loader.js"
MAIN = ROOT / "app/main.py"
FEATURES = ROOT / "app/static/feature-loader.js"


def test_authenticated_boot_is_exactly_app_plus_feature_loader():
    assert _CORE_AUTHENTICATED_SCRIPTS == ["app.js", "feature-loader.js"]


def test_backend_has_no_automatic_deferred_scheduler():
    source = MAIN.read_text(encoding="utf-8")
    loader = source.split("def _authenticated_script_loader()", 1)[1].split("@asynccontextmanager", 1)[0]

    assert "deferredSources" not in loader
    assert "loadDeferred" not in loader
    assert "requestIdleCallback" not in loader
    assert "data-devpilot-progressive" not in loader
    assert "data.devpilotProgressive" not in loader
    assert "script.dataset.devpilotCore = '1'" in loader


def test_legacy_optional_runtime_is_never_part_of_automatic_boot():
    legacy_runtime = (
        "tasks-lazy-load.js",
        "simplified-nav.js",
        "workspace-skins.js",
    )
    for name in legacy_runtime:
        assert name not in _CORE_AUTHENTICATED_SCRIPTS
        assert name not in _DEFERRED_AUTHENTICATED_SCRIPTS

    optional_inventory = (
        "task-analytics.js",
        "build-game.js",
        "mobile-game-mode.js",
        "telemetry-capture.js",
        "token-usage.js",
    )
    for name in optional_inventory:
        assert name not in _CORE_AUTHENTICATED_SCRIPTS
        assert name in _DEFERRED_AUTHENTICATED_SCRIPTS


def test_acs_loader_is_visual_only():
    source = LOADER.read_text(encoding="utf-8")

    assert "body.appendChild =" not in source
    assert "MutationObserver" not in source
    assert "HTMLCollection.prototype.forEach" not in source
    assert "ensureLegacyAuthAnchors" not in source
    assert "loader.style.pointerEvents = 'none'" in source


def test_optional_features_require_explicit_loader_actions():
    source = FEATURES.read_text(encoding="utf-8")

    assert "window.__devpilotLoadFeature = loadFeature" in source
    assert "FEATURE_BUNDLES" in source
    assert "document.addEventListener('click'" in source
    assert "data-devpilot-feature-placeholder" in source
    assert "requestIdleCallback" not in source
    assert "MutationObserver" not in source
