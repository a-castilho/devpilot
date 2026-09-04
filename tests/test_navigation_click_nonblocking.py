from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def navigate_block() -> str:
    return LOADER.split("async function navigateDirect", 1)[1].split("function openTaskDirect", 1)[0]


def test_navigation_changes_view_before_loading_optional_bundle():
    block = navigate_block()
    navigation_positions = [
        pos for marker in ("window.devpilotNavigate(viewName", "showView(viewName);")
        if (pos := block.find(marker)) >= 0
    ]
    assert navigation_positions
    assert min(navigation_positions) < block.index("loadFeature(feature")


def test_navigation_bundle_load_is_nonblocking_and_cancellable():
    block = navigate_block()
    assert "const intentEpoch = navigationEpoch;" in block
    assert "void loadFeature(feature, {intentEpoch})" in block
    assert "await loadFeature(feature" not in block
    assert "intentEpoch !== navigationEpoch" in block
