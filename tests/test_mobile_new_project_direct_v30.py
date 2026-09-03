from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def test_mobile_new_project_uses_direct_view_without_lazy_wait():
    assert "function openProjectBuilderMobileDirect()" in SOURCE
    assert "showViewFallback('new-project')" in SOURCE
    assert "if (isMobilePrimaryAction())" in SOURCE
    assert "openProjectBuilderMobileDirect();" in SOURCE


def test_mobile_direct_path_returns_before_project_builder_lazy_load():
    mobile_branch = SOURCE.index("if (isMobilePrimaryAction())")
    lazy_load = SOURCE.index("window.__devpilotLoadFeature('projectBuilder')")
    assert mobile_branch < lazy_load
    snippet = SOURCE[mobile_branch:lazy_load]
    assert "return;" in snippet


def test_mobile_direct_path_announces_view_change():
    assert "mobile-primary-action-direct" in SOURCE
    assert "devpilot:mobile-new-project-opened" in SOURCE
    assert "__devpilotPrimaryActionSafeOpenV30" in SOURCE
