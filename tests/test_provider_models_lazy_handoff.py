from pathlib import Path


LOADER = Path("app/static/feature-loader.js")
PROVIDERS = Path("app/static/provider-models.js")
APP = Path("app/static/app.js")


def test_provider_navigation_loads_normalized_ui_before_replaying_click():
    loader = LOADER.read_text(encoding="utf-8")
    assert "providers: [" in loader
    assert "'provider-models.js'" in loader
    assert "'provider-ollama.js'" in loader
    assert "['.nav[data-view=\"providers\"]', 'providers']" in loader
    assert "event.stopImmediatePropagation();" in loader
    assert "trigger.dataset.devpilotFeatureReplay = '1'" in loader
    assert "trigger.click();" in loader


def test_provider_models_module_replaces_legacy_loader_with_normalized_loader():
    providers = PROVIDERS.read_text(encoding="utf-8")
    assert "function arrayValue(value)" in providers
    assert "connections=arrayValue(c).map(normalizeConnection).filter(Boolean);" in providers
    assert "try{loadProviders=load}catch(_){}" in providers


def test_regression_documents_legacy_renderer_that_must_not_run_first():
    app = APP.read_text(encoding="utf-8")
    assert "(provider.models || []).map(esc)" in app
    loader = LOADER.read_text(encoding="utf-8")
    providers_trigger = loader.index("['.nav[data-view=\"providers\"]', 'providers']")
    capture_listener = loader.index("document.addEventListener('click', event => {")
    assert providers_trigger < capture_listener
