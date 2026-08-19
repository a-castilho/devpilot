from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


class ModelUnavailable(RuntimeError):
    pass


class LLMClient:
    """Small Ollama-backed chat gateway.

    DevPilot keeps the orchestration and persistence local. The actual transformer model is
    accessed through Ollama's HTTP API, so a 4 GB machine does not need to import heavyweight
    ML frameworks into the API process.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.settings.ollama_chat_enabled:
            raise ModelUnavailable("Ollama chat is disabled")
        try:
            response = httpx.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.settings.ollama_chat_model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=self.settings.model_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("message", {}).get("content")
            if not content:
                raise ModelUnavailable("Model returned an empty response")
            return {
                "content": content,
                "model": payload.get("model", self.settings.ollama_chat_model),
                "provider": "ollama",
                "done_reason": payload.get("done_reason", ""),
            }
        except httpx.HTTPError as error:
            raise ModelUnavailable(f"Ollama chat unavailable: {error}") from error
