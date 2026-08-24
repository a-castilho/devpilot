import pytest

from app.services.ai_routing import economic_ai_route


def test_planning_prefers_local_and_disables_agentic_execution():
    route = economic_ai_route(mode="planning", provider="ollama")

    assert route["strategy"] == "auto-economic"
    assert route["conversation_route"] == "local"
    assert route["conversation_engine"] == "ollama"
    assert route["execution_route"] == "disabled"
    assert route["agentic_execution_started"] is False
    assert route["agentic_budget_preserved"] is True
    assert route["paid_chat_used"] is False


def test_planning_can_fallback_to_chat_without_starting_codex():
    route = economic_ai_route(mode="planning", provider="openai")

    assert route["conversation_route"] == "chat"
    assert route["conversation_engine"] == "openai"
    assert route["execution_route"] == "disabled"
    assert route["agentic_execution_started"] is False
    assert route["paid_chat_used"] is True


def test_build_reserves_codex_for_the_existing_approval_gate():
    route = economic_ai_route(mode="build", provider="ollama")

    assert route["conversation_route"] == "local"
    assert route["execution_route"] == "codex_after_approval"
    assert route["agentic_execution_started"] is False
    assert route["agentic_budget_preserved"] is True


def test_budget_block_forces_local_route_metadata():
    route = economic_ai_route(
        mode="planning",
        provider="ollama",
        budget_forced_local=True,
    )

    assert route["budget_forced_local"] is True
    assert route["paid_chat_used"] is False


def test_unknown_mode_is_rejected_defensively():
    with pytest.raises(ValueError):
        economic_ai_route(mode="unsafe", provider="ollama")  # type: ignore[arg-type]
