import json

from app.services.token_usage import extract_codex_usage, token_counts_from_usage, user_id_from_actor


def test_openai_usage_normalization_keeps_cached_tokens_inside_total():
    counts = token_counts_from_usage(
        {
            "input_tokens": 120,
            "input_tokens_details": {"cached_tokens": 40},
            "output_tokens": 30,
            "total_tokens": 150,
        }
    )
    assert counts.input_tokens == 120
    assert counts.cached_input_tokens == 40
    assert counts.output_tokens == 30
    assert counts.total_tokens == 150


def test_google_usage_normalization():
    counts = token_counts_from_usage(
        {
            "promptTokenCount": 80,
            "cachedContentTokenCount": 20,
            "candidatesTokenCount": 15,
            "totalTokenCount": 95,
        }
    )
    assert counts.as_dict() == {
        "input_tokens": 80,
        "cached_input_tokens": 20,
        "output_tokens": 15,
        "total_tokens": 95,
    }


def test_codex_uses_last_completed_turn_usage():
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "abc"}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 25, "cached_input_tokens": 5, "output_tokens": 4, "total_tokens": 29}}),
        ]
    )
    counts = extract_codex_usage(stdout)
    assert counts.total_tokens == 29
    assert counts.input_tokens == 25
    assert counts.cached_input_tokens == 5
    assert counts.output_tokens == 4


def test_usage_is_not_estimated_without_provider_metadata():
    assert token_counts_from_usage(None).total_tokens == 0
    assert extract_codex_usage('{"type":"item.completed","text":"ok"}').total_tokens == 0


def test_user_id_is_resolved_only_from_user_actor():
    assert user_id_from_actor("user:abc-123") == "abc-123"
    assert user_id_from_actor("worker") is None
    assert user_id_from_actor("owner") is None
