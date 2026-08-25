from pathlib import Path


CHAT_CONTROL = Path("app/static/super-admin-chat-control.js")
MAIN = Path("app/main.py")
WORKSPACE_SKINS = Path("app/static/workspace-skins.js")


def test_post_login_does_not_release_global_deferred_loader_automatically():
    source = CHAT_CONTROL.read_text(encoding="utf-8")

    assert "deferredReleased: false" in source
    assert "releaseDeferred()" in source
    assert "await refreshControl();" in source
    assert "control.releaseDeferred()" not in source
    assert "resolveReady(control)" not in source


def test_base_views_load_only_their_feature_bundle_on_user_intent():
    source = CHAT_CONTROL.read_text(encoding="utf-8")

    assert "const FEATURE_BUNDLES" in source
    assert "projects:" in source
    assert "tasks:" in source
    assert "providers:" in source
    assert "reports:" in source
    assert "audit:" in source
    assert "window.__devpilotLoadFeature = loadBundle" in source
    assert "document.addEventListener('click'" in source
    assert "void loadBundle(String(nav.dataset.view || ''))" in source


def test_development_base_bundle_keeps_heavy_modules_cold():
    source = CHAT_CONTROL.read_text(encoding="utf-8")
    feature_block = source.split("const FEATURE_BUNDLES = {", 1)[1].split("};", 1)[0]
    tasks_block = feature_block.split("tasks:", 1)[1].split("],", 1)[0]

    assert "tasks-lazy-load.js" in tasks_block
    assert "task-analytics.js" not in tasks_block
    assert "task-failures.js" not in tasks_block
    assert "approval-slider.js" not in tasks_block
    assert "analysis-commercial-proposal.js" not in tasks_block
    assert "task-advanced" in feature_block
    assert "task-analysis" in feature_block
    assert "Carregar gráficos e diagnósticos" in source


def test_workspace_skin_does_not_observe_entire_dom():
    source = WORKSPACE_SKINS.read_text(encoding="utf-8")
    assert "MutationObserver" not in source
    assert "subtree: true" not in source


def test_global_loader_still_waits_for_chat_control_ready_gate():
    source = MAIN.read_text(encoding="utf-8")

    assert "const chatControl = window.__devpilotChatControl" in source
    assert "await chatControl.ready" in source
    assert "await sleep(900)" in source


def test_overview_bundle_is_intentionally_absent():
    source = CHAT_CONTROL.read_text(encoding="utf-8")

    feature_block = source.split("const FEATURE_BUNDLES = {", 1)[1].split("};", 1)[0]
    assert "overview:" not in feature_block
