from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_zoom_compensation_tracks_real_ratio():
    source = read("viewport-adaptive-v15.js")
    assert "Math.min(2.25" in source
    assert "Math.min(1.42" not in source
    assert "data-layout-scale-v36" in source
    assert "layout-scale-v36.css" in source
    assert "dataset.dpBoost" in source


def test_v36_removes_legacy_width_caps():
    css = read("layout-scale-v36.css")
    assert "#new-project-view" in css
    assert "#project-builder-form" in css
    assert "max-width: none !important" in css
    assert "--dp-zoom-scale" in css


def test_compact_desktop_executions_use_cards_not_squeezed_columns():
    css = read("layout-scale-v36.css")
    assert "@media (min-width: 901px) and (max-width: 1180px)" in css
    assert "#tasks-view .tasks-v9-table thead" in css
    assert "display: none !important" in css
    assert "grid-template-columns: minmax(0, 1fr) auto !important" in css
    assert "word-break: normal !important" in css
    assert "overflow-wrap: normal !important" in css


def test_zoomed_builder_cards_scale_with_boost():
    css = read("layout-scale-v36.css")
    assert "calc(205px * var(--dp-zoom-scale))" in css
    assert "calc(96px * var(--dp-zoom-scale))" in css
    assert "calc(14px * var(--dp-zoom-scale))" in css
