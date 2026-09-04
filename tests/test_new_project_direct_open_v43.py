from pathlib import Path


SOURCE = Path("app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def _open_block() -> str:
    return SOURCE.split("function openProjectBuilderSafe()", 1)[1].split(
        "function openTaskModalSafe", 1
    )[0]


def test_new_project_direct_open_bypasses_legacy_navigation():
    block = _open_block()
    assert "showViewFallback('new-project')" in block
    assert "window.devpilotNavigate" not in block
    assert "window.showView" not in block


def test_new_project_paints_before_loading_builder():
    block = _open_block()
    assert block.index("showViewFallback('new-project')") < block.index("requestAnimationFrame")
    assert block.index("requestAnimationFrame") < block.index("__devpilotLoadFeature('projectBuilder')")


def test_new_project_capture_handler_stops_legacy_handlers():
    assert "__devpilotPrimaryActionSafeOpenV30" in SOURCE
    assert "event.stopImmediatePropagation()" in SOURCE
    assert "}, true);" in SOURCE
