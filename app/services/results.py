from __future__ import annotations

import json
from typing import Any


TOKEN_KEYS = {"input_tokens", "output_tokens", "cached_input_tokens", "total_tokens"}


def _json_events(output: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _usage_candidates(value: Any) -> list[dict[str, int]]:
    candidates: list[dict[str, int]] = []
    if isinstance(value, dict):
        numeric = {
            key: int(item)
            for key, item in value.items()
            if key in TOKEN_KEYS and isinstance(item, (int, float))
        }
        if numeric:
            candidates.append(numeric)
        for item in value.values():
            candidates.extend(_usage_candidates(item))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_usage_candidates(item))
    return candidates


def extract_usage(output: str) -> dict[str, int]:
    candidates = [item for event in _json_events(output) for item in _usage_candidates(event)]
    if not candidates:
        return {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "total_tokens": 0}
    usage = max(
        candidates,
        key=lambda item: item.get("total_tokens", item.get("input_tokens", 0) + item.get("output_tokens", 0)),
    )
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": usage.get("cached_input_tokens", 0),
        "total_tokens": usage.get("total_tokens", input_tokens + output_tokens),
    }


def extract_summary(output: str) -> str:
    for event in reversed(_json_events(output)):
        item = event.get("item") if isinstance(event.get("item"), dict) else event
        if item.get("type") not in {"agent_message", "message", "assistant_message"}:
            continue
        for key in ("text", "content", "message", "output_text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[-20_000:]
    return output.strip()[-8_000:] or "Execução concluída sem resumo textual."
