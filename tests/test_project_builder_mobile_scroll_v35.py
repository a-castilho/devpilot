from pathlib import Path

CSS = Path("app/static/mobile-scroll-unlock.css").read_text(encoding="utf-8")


def test_mobile_builder_restores_horizontal_choice_strips():
    assert "Cadastro de projeto mobile V35" in CSS
    assert "#project-builder-form .choice-strip" in CSS
    assert "display: flex !important" in CSS
    assert "overflow-x: auto !important" in CSS
    assert "scroll-snap-type: x proximity !important" in CSS


def test_mobile_builder_checkbox_does_not_inherit_full_width_input():
    assert '#project-builder-form .builder-delivery .check input[type="checkbox"]' in CSS
    assert "width: 22px !important" in CSS
    assert "height: 22px !important" in CSS
    assert "flex: 0 0 22px !important" in CSS


def test_mobile_builder_skips_offscreen_layout_work():
    assert "content-visibility: auto" in CSS
    assert "contain-intrinsic-size: auto 240px" in CSS
