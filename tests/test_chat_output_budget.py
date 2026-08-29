from app.services.chat_http_client import (
    CHAT_MAX_OUTPUT_TOKENS,
    CHAT_TEXT_DEFAULT_OUTPUT_TOKENS,
    CHAT_VOICE_DEFAULT_OUTPUT_TOKENS,
    apply_chat_output_budget,
    chat_output_token_limit,
)


def test_text_and_voice_chat_have_independent_default_output_budgets(monkeypatch):
    monkeypatch.delenv("DEVPILOT_CHAT_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("DEVPILOT_CHAT_VOICE_MAX_OUTPUT_TOKENS", raising=False)

    assert chat_output_token_limit("chat") == CHAT_TEXT_DEFAULT_OUTPUT_TOKENS == 2048
    assert chat_output_token_limit("voice") == CHAT_VOICE_DEFAULT_OUTPUT_TOKENS == 320


def test_chat_output_budget_is_configurable_but_clamped(monkeypatch):
    monkeypatch.setenv("DEVPILOT_CHAT_MAX_OUTPUT_TOKENS", "4096")
    assert chat_output_token_limit("chat") == 4096

    monkeypatch.setenv("DEVPILOT_CHAT_MAX_OUTPUT_TOKENS", "999999")
    assert chat_output_token_limit("chat") == CHAT_MAX_OUTPUT_TOKENS == 8192

    monkeypatch.setenv("DEVPILOT_CHAT_MAX_OUTPUT_TOKENS", "invalid")
    assert chat_output_token_limit("chat") == CHAT_TEXT_DEFAULT_OUTPUT_TOKENS


def test_chat_budget_rewrites_all_existing_provider_payload_shapes():
    assert apply_chat_output_budget({"max_output_tokens": 280}, 2048)["max_output_tokens"] == 2048
    assert apply_chat_output_budget({"max_tokens": 280}, 2048)["max_tokens"] == 2048
    assert apply_chat_output_budget(
        {"generationConfig": {"maxOutputTokens": 280, "temperature": 0.2}},
        2048,
    )["generationConfig"] == {"maxOutputTokens": 2048, "temperature": 0.2}
    assert apply_chat_output_budget(
        {"options": {"num_predict": 280, "temperature": 0.2}},
        2048,
    )["options"] == {"num_predict": 2048, "temperature": 0.2}
