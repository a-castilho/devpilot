import os
import re
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from app.telemetry_replay import clean_pointer, timeline_event


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pointer_coordinates_are_coarse_and_clamped():
    assert clean_pointer({"grid_x": 200, "grid_y": -30}) == {"grid_x": 19, "grid_y": 0}
    assert clean_pointer({"grid_x": "7", "grid_y": "12"}) == {"grid_x": 7, "grid_y": 12}
    assert clean_pointer({"grid_x": "x", "grid_y": None}) == {"grid_x": 0, "grid_y": 0}


def test_timeline_event_returns_only_stored_sanitized_payload():
    row = SimpleNamespace(
        id=3,
        source="terminal",
        event_type="command",
        occurred_at="2026-08-21T10:00:00+00:00",
        payload='{"command":"git status","cwd":"~/Documents/devpilot","exit_code":0}',
    )
    item = timeline_event(row)
    assert item["source"] == "terminal"
    assert item["event_type"] == "command"
    assert item["payload"]["command"] == "git status"
    assert "fingerprint" not in item


def test_replay_frontend_is_visual_only_and_captures_pointer_motion():
    replay = read("app/static/telemetry-replay.js")
    capture = read("app/static/telemetry-replay-capture.js")
    html = read("app/static/telemetry.html")

    assert "/timeline?limit=5000" in replay
    assert "Simulação somente visual" in replay
    assert "pointermove" in capture
    assert "/pointer" in capture
    assert "dispatchEvent" not in replay
    assert ".click(" not in replay
    assert "/assets/telemetry-replay.css" in html
    assert "/assets/telemetry-replay-capture.js" in html
    assert "/assets/telemetry-replay.js" in html


def test_spa_keeps_replay_capture_lazy_and_router_is_registered():
    main = read("app/main.py")
    loader = read("app/static/feature-loader.js")

    assert "telemetry_replay_router" in main
    assert "app.include_router(telemetry_replay_router)" in main
    assert "/assets/telemetry-replay-capture.js" not in main

    audit_bundle = re.search(r"audit:\s*\[(.*?)\]", loader, re.DOTALL)
    assert audit_bundle is not None
    assets = re.findall(r"'([^']+\.js)'", audit_bundle.group(1))
    assert "telemetry-capture.js" in assets
    assert "telemetry-replay-capture.js" in assets
