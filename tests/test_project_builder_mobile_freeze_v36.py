from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static" / "project-provisioning.js"


def source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_mobile_builder_hides_group_host_before_heavy_render():
    js = source()
    assert "initMobileBuilderPerformanceGuard" in js
    assert "groupsHost.style.setProperty('display', 'none', 'important')" in js
    assert "new MutationObserver" in js
    assert "mobileAccordionReady" in js


def test_mobile_builder_disables_live_heavy_summary_and_preview():
    js = source()
    assert "summary.removeAttribute('id')" in js
    assert "preview.removeAttribute('id')" in js
    assert "buildBuilderAgentsMd" in js
    assert "previewText || buildBuilderAgentsMd(form, blueprint)" in js


def test_mobile_builder_keeps_one_option_group_open_at_a_time():
    js = source()
    assert "builder-mobile-group-toggle" in js
    assert "closeOtherGroups" in js
    assert "strip.style.setProperty('display', 'none', 'important')" in js
    assert "Abra uma categoria por vez" in js
