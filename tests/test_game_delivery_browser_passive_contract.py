from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "app/static/game/delivery-gate.js"
OBSERVER = ROOT / "app/static/game/stable-delivery-url.js"
PROJECTS = ROOT / "app/static/project-auto-delivery.js"
MOBILE = ROOT / "app/static/mobile-project-card-compact.js"


def test_game_delivery_gate_never_advances_cloud_state_in_browser():
    source = GATE.read_text(encoding="utf-8")
    assert "/delivery/auto" not in source
    assert "scheduleDeliveryRetry" not in source
    assert "observeAutomaticDelivery" in source


def test_stable_delivery_url_is_passive_visible_only_observer():
    source = OBSERVER.read_text(encoding="utf-8")
    assert "WATCH_MS = 30000" in source
    assert "document.visibilityState" in source
    assert "/delivery/start" not in source
    assert "/delivery/retry" not in source
    assert "/delivery/validate-url" not in source
    assert "method: 'POST'" not in source


def test_project_surfaces_do_not_compete_with_delivery_worker():
    assert "/delivery/auto" not in PROJECTS.read_text(encoding="utf-8")
    assert "/delivery/auto" not in MOBILE.read_text(encoding="utf-8")
