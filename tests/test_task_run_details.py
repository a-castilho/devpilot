import json
from types import SimpleNamespace

from app.task_run_routes import failure_reason, sanitize_text


def test_failure_reason_prefers_last_stderr_line():
    run = SimpleNamespace(
        status="failed",
        summary="Execution completed on an isolated task branch after duplicate preflight.",
        logs=json.dumps({"stderr": "warning\nfatal: repository access denied"}),
    )

    assert failure_reason(run) == "fatal: repository access denied"


def test_failure_reason_falls_back_to_summary():
    run = SimpleNamespace(status="failed", summary="Codex quota exceeded", logs="")

    assert failure_reason(run) == "Codex quota exceeded"


def test_sanitize_text_redacts_common_credentials():
    text = "Authorization: Bearer secret-token github_pat_ABC123456789"

    sanitized = sanitize_text(text)

    assert "secret-token" not in sanitized
    assert "github_pat_ABC123456789" not in sanitized
    assert "[REDACTED]" in sanitized
