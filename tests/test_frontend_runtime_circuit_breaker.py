from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_optional_features_are_loaded_only_on_explicit_user_action():
    runtime = read("app/static/workspace-skins.js")

    assert "installDeferredCircuitBreaker" in runtime
    assert "node.dataset.devpilotProgressive === '1'" in runtime
    assert "boot?.phase === 'deferred'" in runtime
    assert "window.__devpilotLoadFeature = loadFeature" in runtime
    assert "FEATURE_BUNDLES" in runtime
    assert "data-nav-group-toggle=\"super-admin\"" in runtime
    assert "data-view=\"projects\"" in runtime
    assert "data-view=\"tasks\"" in runtime


def test_feature_loader_does_not_reintroduce_global_dom_observer():
    runtime = read("app/static/workspace-skins.js")

    assert "MutationObserver" not in runtime
    assert "subtree: true" not in runtime


def test_acs_loader_never_locks_body_or_pointer_input():
    loader = read("app/static/acs-loader.js")

    assert "document.body.style.overflow = 'hidden'" not in loader
    assert "loader.style.pointerEvents = 'none'" in loader
    assert "devpilot:authenticated-core-ready" in loader
    assert "window.setTimeout(removeNow, 1400)" in loader


def test_token_usage_polling_is_not_part_of_core_boot():
    main = read("app/main.py")
    core_block = main.split("_CORE_AUTHENTICATED_SCRIPTS = [", 1)[1].split("]", 1)[0]

    assert '"token-usage.js"' not in core_block
    assert '"cloud-admin.js"' not in core_block
    assert '"linux-terminal.js"' not in core_block
