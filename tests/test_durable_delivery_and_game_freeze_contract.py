from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "app/services/delivery_recovery_worker.py"
WORKER_ENTRY = ROOT / "app/worker_entry.py"
BOOTSTRAP = ROOT / "app/static/game/game-bootstrap.js"
STABLE = ROOT / "app/static/game/stable-delivery-url.js"
FINAL_GATE = ROOT / "app/static/game/final-delivery-gate.js"


def test_delivery_recovery_is_owned_by_backend_worker():
    assert RECOVERY.exists(), "delivery recovery must continue without an open browser"
    recovery = RECOVERY.read_text(encoding="utf-8")
    worker_entry = WORKER_ENTRY.read_text(encoding="utf-8")

    assert "process_delivery_recovery_once" in recovery
    assert "start_delivery_recovery_worker" in recovery
    assert "blocked" in recovery and "failed" in recovery
    assert "deploying" in recovery and "provisioning" in recovery
    assert "delivery.run_delivery" in recovery
    assert "start_delivery_recovery_worker()" in worker_entry


def test_game_has_only_one_delivery_orchestrator():
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    stable = STABLE.read_text(encoding="utf-8")

    # delivery-gate.js is the only browser-side orchestrator. The stable surface is observer-only.
    assert "'game/delivery-gate.js'" in bootstrap
    assert "build-game-url-bonus.js" not in bootstrap
    assert "method: 'POST'" not in stable
    assert "/validate-url" not in stable
    assert "MutationObserver" not in stable


def test_final_gate_uses_explicit_events_instead_of_document_wide_observer():
    source = FINAL_GATE.read_text(encoding="utf-8")
    assert "MutationObserver" not in source
    assert "devpilot:delivery:updated" in source
    assert "devpilot:delivery:ready" in source


def test_victory_keeps_read_only_delivery_summary():
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert "game/final-delivery-summary.js" in bootstrap
