from __future__ import annotations

from app.services.recovery import AutoRecoveryService

_ORIGINAL_CLASSIFY = AutoRecoveryService.classify


def _classify(self: AutoRecoveryService, error_text: str) -> str:
    text = str(error_text or "").casefold()
    codex_signals = (
        "api.openai.com/v1/responses",
        "responses_websocket",
        "missing bearer or basic authentication",
        "codex login",
        "invalid api key",
    )
    if any(signal in text for signal in codex_signals) and (
        "401" in text or "unauthorized" in text or "authentication" in text
    ):
        return "codex_auth"
    return _ORIGINAL_CLASSIFY(self, error_text)


def install() -> None:
    if getattr(AutoRecoveryService.classify, "_devpilot_codex_classification", False):
        return
    _classify._devpilot_codex_classification = True
    AutoRecoveryService.classify = _classify


install()
