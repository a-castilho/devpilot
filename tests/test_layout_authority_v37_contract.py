from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_viewport_loads_v37_after_v36():
    source = read("viewport-adaptive-v15.js")
    v36 = source.index("layout-scale-v36.css")
    v37 = source.index("layout-authority-v37.css")
    assert v37 > v36
    assert "data-layout-authority-v37" in source
    assert "Viewport Adaptive V37" in source


def test_v37_owns_full_width_and_overflow_rules():
    css = read("layout-authority-v37.css")
    assert "DevPilot Layout Authority V37" in css
    assert "overflow-x: hidden" in css
    assert "overflow-x: clip" in css
    assert "#new-project-view" in css
    assert "#tasks-view" in css
    assert "max-width: none !important" in css


def test_v37_keeps_builder_readable_on_compact_desktop():
    css = read("layout-authority-v37.css")
    assert "@media (min-width: 901px) and (max-width: 1280px)" in css
    assert "#project-builder-form.project-builder" in css
    assert "grid-template-columns: minmax(0, 1fr) !important" in css
    assert ".choice-strip" in css
    assert "overflow: visible !important" in css


def test_v37_prevents_execution_column_collapse():
    css = read("layout-authority-v37.css")
    assert "word-break: normal !important" in css
    assert "overflow-wrap: normal !important" in css
    assert "#tasks-view .tasks-v9-table thead" in css
    assert "display: none !important" in css
    assert "#tasks-view .tasks-v9-row" in css
    assert "grid-template-columns: minmax(0, 1fr) auto !important" in css


def test_v37_preserves_mobile_single_column_authority():
    css = read("layout-authority-v37.css")
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 520px)" in css
    assert ".project-builder-aside" in css
    assert "position: static !important" in css
