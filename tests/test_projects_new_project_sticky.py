from pathlib import Path


SCRIPT = Path("app/static/product-delivery-ui.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_projects_keep_new_project_entry_visible():
    text = source()
    assert "projects-new-project-sticky" in text
    assert "+ Novo projeto" in text
    assert "position:sticky" in text
    assert "ensureCreateEntry" in text


def test_new_project_entry_loads_builder_before_opening():
    text = source()
    assert "__devpilotLoadFeature('projectBuilder')" in text
    assert "[data-project-builder-open]" in text
    assert "originalEntry.click()" in text


def test_new_project_entry_recovers_after_rerender():
    text = source()
    assert "MutationObserver" in text
    assert "observer.observe(view, {childList:true, subtree:true})" in text
    assert "ensureCreateEntry();" in text
