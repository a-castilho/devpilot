from app.chat_mode_routes import _chat_provider_order


def test_chat_tries_local_ollama_before_registered_cloud_providers():
    assert _chat_provider_order(["openai", "google", "anthropic", "ollama"]) == [
        "ollama",
        "openai",
        "google",
        "anthropic",
    ]


def test_chat_provider_order_deduplicates_and_normalizes_values():
    assert _chat_provider_order(["OLLAMA", "openai", "openai", "google"]) == [
        "ollama",
        "openai",
        "google",
    ]
