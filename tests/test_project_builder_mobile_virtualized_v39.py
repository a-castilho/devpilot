from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "app/static/project-builder-mobile-runtime-v39.js").read_text(encoding="utf-8")
SHIPS = (ROOT / "app/static/mobile-game-ships-stable.js").read_text(encoding="utf-8")


def test_mobile_builder_virtualizes_closed_groups_without_losing_selected_nodes():
    assert "Project Builder Mobile V39 virtualizado" in RUNTIME
    assert "document.createDocumentFragment()" in RUNTIME
    assert "if (!node.classList?.contains('selected')) cache.appendChild(node)" in RUNTIME
    assert "record.strip.replaceChildren(...record.nodes)" in RUNTIME
    assert "record.strip.style.removeProperty('display')" in RUNTIME


def test_mobile_builder_removes_live_counter_and_heavy_compositor_helpers():
    assert "count.removeAttribute('id')" in RUNTIME
    assert 'html[data-devpilot-view="new-project"] body .voice-dock {display:none!important}' in RUNTIME
    assert "backdrop-filter:none!important" in RUNTIME


def test_mobile_ship_runtime_no_longer_observes_entire_document():
    assert "observer.observe(document.documentElement" not in SHIPS
    assert "projectsObserver.observe(host, {childList:true, subtree:true})" in SHIPS
    assert "if (!isMobile() || !projectsViewActive()) return" in SHIPS


def test_mobile_ship_runtime_loads_builder_v39():
    assert "ensureBuilderRuntime" in SHIPS
    assert "/assets/project-builder-mobile-runtime-v39.js?v=20260903-v39" in SHIPS
