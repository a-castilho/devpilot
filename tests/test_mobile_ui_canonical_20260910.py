from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/static/mobile-ui-canonical-20260910.css").read_text(encoding="utf-8")
BUILD = (ROOT / "tools/build-vercel-static.mjs").read_text(encoding="utf-8")


def test_canonical_mobile_stylesheet_is_last_vercel_authority():
    assert "'mobile-ui-canonical-20260910.css'" in BUILD
    assert BUILD.index("'super-admin-voice.css'") < BUILD.index("'mobile-ui-canonical-20260910.css'")
    assert "name === 'mobile-ui-canonical-20260910.css'" in BUILD
    assert "revision(assetPath)" in BUILD


def test_mobile_uses_dynamic_viewport_and_single_vertical_flow():
    assert "min-height: 100svh" in CSS
    assert "min-height: 100dvh" in CSS
    assert "body:not(.mobile-simple-open)" in CSS
    assert "overflow-y: auto !important" in CSS
    assert "#tasks-view" in CSS
    assert "height: auto !important" in CSS
    assert "overflow: visible !important" in CSS


def test_mobile_navigation_has_five_stable_columns_and_safe_area():
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in CSS
    assert "env(safe-area-inset-bottom)" in CSS
    assert "text-overflow: ellipsis" in CSS
    assert "position: fixed !important" in CSS


def test_execution_cards_override_legacy_ship_layout_compactly():
    assert "#tasks-view #tasks-table > tr.tasks-v9-row" in CSS
    assert "#tasks-view #tasks-table > tr.tasks-render-stable-v40" in CSS
    assert "grid-template-columns: minmax(0, 1fr) auto" in CSS
    assert "min-height: 0 !important" in CSS
    assert "font-size: 16px !important" in CSS
    assert "-webkit-line-clamp: 2" in CSS
    assert "content: none !important" in CSS


def test_mobile_projects_and_builder_cannot_create_horizontal_scroll():
    assert "#projects-list" in CSS
    assert "grid-template-columns: minmax(0, 1fr)" in CSS
    assert "#new-project-view .project-builder" in CSS
    assert "max-width: 100% !important" in CSS
    assert "overflow-x: hidden !important" in CSS
