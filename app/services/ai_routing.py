from __future__ import annotations

from typing import Literal


ChatMode = Literal["planning", "build"]


def economic_ai_route(
    *,
    mode: ChatMode,
    provider: str,
    budget_forced_local: bool = False,
) -> dict[str, object]:
    """Describe the cost-aware route used by the interactive DevPilot chat.

    The chat endpoint never starts the agentic executor itself. Planning keeps
    execution disabled. Build mode may stage an approved task, but Codex is only
    eligible after the task passes the existing approval gate.
    """
    normalized_provider = str(provider or "").strip().lower()
    if mode not in {"planning", "build"}:
        raise ValueError(f"Unsupported chat mode: {mode}")

    local = normalized_provider == "ollama"
    execution_route = "disabled" if mode == "planning" else "codex_after_approval"

    return {
        "strategy": "auto-economic",
        "conversation_route": "local" if local else "chat",
        "conversation_engine": "ollama" if local else normalized_provider,
        "execution_route": execution_route,
        "agentic_execution_started": False,
        "agentic_budget_preserved": True,
        "paid_chat_used": not local,
        "budget_forced_local": bool(budget_forced_local),
    }
