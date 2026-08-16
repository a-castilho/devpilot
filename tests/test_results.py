import json

from app.services.results import extract_summary, extract_usage


def jsonl(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events)


def test_extracts_final_usage_from_codex_json_events():
    output = jsonl(
        {"type": "turn.started"},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 350,
            },
        },
    )

    assert extract_usage(output) == {
        "input_tokens": 1200,
        "cached_input_tokens": 800,
        "output_tokens": 350,
        "total_tokens": 1550,
    }


def test_extracts_last_agent_message_as_report_summary():
    output = jsonl(
        {"item": {"type": "agent_message", "text": "Primeiro progresso"}},
        {"item": {"type": "agent_message", "text": "Entrega concluída e testes passando"}},
    )

    assert extract_summary(output) == "Entrega concluída e testes passando"


def test_invalid_json_does_not_create_fake_usage():
    assert extract_usage("not-json") == {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
