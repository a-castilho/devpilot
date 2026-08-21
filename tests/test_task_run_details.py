import json
from types import SimpleNamespace

from app.task_run_routes import (
    classify_failure_text,
    failure_details,
    failure_reason,
    router,
    sanitize_text,
)


def test_failure_reason_converts_repository_access_denied_to_client_message():
    run = SimpleNamespace(
        status="failed",
        summary="Execution completed on an isolated task branch after duplicate preflight.",
        logs=json.dumps({"stderr": "warning\nfatal: repository access denied"}),
    )

    reason = failure_reason(run)

    assert reason.startswith("Credencial GitHub sem acesso ao repositório")
    assert "fatal:" not in reason


def test_failure_details_classifies_github_403_without_exposing_raw_git_error():
    run = SimpleNamespace(
        status="failed",
        summary="Execution failed",
        logs=json.dumps(
            {
                "stderr": (
                    "fatal: unable to access 'https://github.com/a-castilho/devpilot.git/': "
                    "The requested URL returned error: 403"
                )
            }
        ),
    )

    details = failure_details(run)

    assert details["category"] == "github_auth"
    assert details["code"] == "GITHUB_ACCESS_DENIED"
    assert details["requires_authorization"] is True
    assert "403" not in details["message"]


def test_failure_details_prefers_self_healing_message():
    run = SimpleNamespace(
        status="failed",
        summary="Execution failed",
        logs=json.dumps(
            {
                "stderr": "The requested URL returned error: 403",
                "self_healing": {
                    "category": "github_auth",
                    "message": "As credenciais GitHub foram testadas e nenhuma possui acesso.",
                    "requires_authorization": True,
                },
            }
        ),
    )

    details = failure_details(run)

    assert details["message"] == "As credenciais GitHub foram testadas e nenhuma possui acesso."
    assert details["category"] == "github_auth"
    assert details["requires_authorization"] is True


def test_failure_reason_falls_back_to_summary():
    run = SimpleNamespace(status="failed", summary="Codex quota exceeded", logs="")

    assert failure_reason(run) == "Codex quota exceeded"


def test_classify_failure_text_recognizes_common_auth_errors():
    assert classify_failure_text("The requested URL returned error: 403") == "github_auth"
    assert classify_failure_text("Not logged in. Run codex login") == "codex_auth"


def test_sanitize_text_redacts_common_credentials():
    text = "Authorization: Bearer secret-token github_pat_ABC123456789"

    sanitized = sanitize_text(text)

    assert "secret-token" not in sanitized
    assert "github_pat_ABC123456789" not in sanitized
    assert "[REDACTED]" in sanitized


def test_router_exposes_same_task_retry_without_creating_a_new_task():
    retry_routes = [
        route
        for route in router.routes
        if getattr(route, "path", "") == "/api/tasks/{task_id}/retry"
    ]

    assert len(retry_routes) == 1
    assert "POST" in retry_routes[0].methods
