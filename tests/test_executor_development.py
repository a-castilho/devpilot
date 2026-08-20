from types import SimpleNamespace

from app.services.executor import (
    CODEX_AUTH_FAILURE_MARKERS,
    DEVELOPMENT_DUPLICATE_GUARD,
    codex_authentication_rejected,
    development_prompt,
)


def test_development_prompt_starts_with_duplicate_preflight_before_changes():
    task = SimpleNamespace(title="Desenvolver menu", prompt="Adicione o menu solicitado.")
    prompt = development_prompt(task)
    assert "DUPLICATION PREFLIGHT" in DEVELOPMENT_DUPLICATE_GUARD
    assert "Do not create a parallel or second implementation" in prompt
    assert "If the feature already exists completely" in prompt
    assert prompt.index("DUPLICATION PREFLIGHT") < prompt.index("Only after completing that preflight")


def test_codex_401_is_detected_without_exposing_authentication_details():
    stderr = "error: websocket failed to connect: HTTP 401 Unauthorized"
    assert "unauthorized" in CODEX_AUTH_FAILURE_MARKERS
    assert codex_authentication_rejected("", stderr) is True
    assert codex_authentication_rejected("completed", "") is False
