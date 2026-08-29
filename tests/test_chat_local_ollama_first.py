from app.chat_mode_routes import _chat_provider_order


def test_chat_respects_configured_remote_order_and_keeps_ollama_as_fallback():
    assert _chat_provider_order(["openai", "google", "anthropic", "ollama"]) == [
        "openai",
        "google",
        "anthropic",
        "ollama",
    ]


def test_chat_provider_order_deduplicates_normalizes_and_adds_local_fallback():
    assert _chat_provider_order(["OPENAI", "openai", "google"]) == [
        "openai",
        "google",
        "ollama",
    ]
