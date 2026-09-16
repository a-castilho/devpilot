from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "app/static/game/game-bootstrap.js"
AUTO = ROOT / "app/static/game/delivery-auto-progress.js"


def test_auto_progress_asset_is_loaded_after_stable_delivery_ui():
    boot = BOOT.read_text(encoding="utf-8")
    assert "game/delivery-auto-progress.js" in boot
    assert boot.index("game/stable-delivery-url.js") < boot.index("game/delivery-auto-progress.js")


def test_auto_progress_continues_backend_state_machine_until_real_url_is_ready():
    source = AUTO.read_text(encoding="utf-8")
    assert "`${endpoint(projectId)}/auto`" in source
    assert "method: 'POST'" in source
    assert "normalized(state?.status) === 'ready'" in source
    assert r"/^https:\/\//i" in source
    assert "schedule(projectId" in source
    assert "devpilot:game:delivery-ready" in source


def test_auto_progress_does_not_require_operator_role_in_browser():
    source = AUTO.read_text(encoding="utf-8")
    assert "SUPER_ADMIN" not in source
    assert "OWNER" not in source
    assert "ADMIN" not in source
    assert "window.api" in source
