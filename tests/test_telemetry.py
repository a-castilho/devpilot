import json
import os
from types import SimpleNamespace

os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from sqlalchemy import create_engine, inspect

import app.telemetry  # noqa: F401
from app.db import Base
from app.telemetry import build_analysis, redact_command, sanitize_browser_payload


def test_telemetry_schema_is_registered():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert "telemetry_sessions" in tables
    assert "telemetry_events" in tables


def test_terminal_command_redacts_common_secrets():
    command = (
        "API_KEY=sk-1234567890abcdefghijkl curl "
        "--token github_pat_ABC123DEF456 https://user:password@example.com/private"
    )
    redacted = redact_command(command)
    assert "sk-1234567890abcdefghijkl" not in redacted
    assert "github_pat_ABC123DEF456" not in redacted
    assert "user:password@" not in redacted
    assert "API_KEY=***" in redacted
    assert "--token ***" in redacted


def test_browser_payload_never_keeps_typed_value_or_text_content():
    clean, fingerprint = sanitize_browser_payload(
        "key",
        {
            "group": "text",
            "value": "senha-super-secreta",
            "text": "conteudo digitado",
            "ctrl": False,
            "shift": True,
        },
    )
    assert "value" not in clean
    assert "text" not in clean
    assert "senha-super-secreta" not in json.dumps(clean)
    assert fingerprint.startswith("key:text:")


def event(source, event_type, payload, fingerprint):
    return SimpleNamespace(
        source=source,
        event_type=event_type,
        payload=json.dumps(payload),
        fingerprint=fingerprint,
    )


def test_analysis_finds_repeated_terminal_and_browser_flow():
    rows = [
        event("terminal", "command", {"command": "git status"}, "terminal:a"),
        event("terminal", "command", {"command": "pytest -q"}, "terminal:b"),
        event("browser", "click", {"grid_x": 3, "grid_y": 4}, "click:button::left:3:4"),
        event("terminal", "command", {"command": "git status"}, "terminal:a"),
        event("terminal", "command", {"command": "pytest -q"}, "terminal:b"),
        event("browser", "click", {"grid_x": 3, "grid_y": 4}, "click:button::left:3:4"),
    ]
    analysis = build_analysis(rows)
    assert analysis["automation_score"] > 0
    assert analysis["patterns"]["terminal_sequences"]
    assert analysis["patterns"]["clicks"]
    assert analysis["candidates"][0]["kind"] == "hybrid_workflow"
    assert analysis["privacy"]["typed_content_stored"] is False
