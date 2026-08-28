from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


_SETTING_KEY = "global"


def load_runtime_settings(engine: Engine) -> dict[str, Any]:
    if engine.dialect.name != "postgresql":
        return {}
    try:
        with engine.connect() as connection:
            raw = connection.execute(
                text("SELECT value FROM rag_runtime_settings WHERE key=:key"),
                {"key": _SETTING_KEY},
            ).scalar_one_or_none()
    except Exception:
        return {}
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_runtime_settings(engine: Engine, settings: dict[str, Any]) -> None:
    if engine.dialect.name != "postgresql":
        return
    payload = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO rag_runtime_settings (key, value, updated_at)
                VALUES (:key, CAST(:value AS jsonb), NOW())
                ON CONFLICT (key)
                DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """
            ),
            {"key": _SETTING_KEY, "value": payload},
        )
