from pathlib import Path

import pytest
from pydantic import ValidationError

from app.chat_mode_routes import CHAT_PROFILES, DevPilotChatRequest, _mode_instructions


SCRIPT = Path("app/static/voice-chatgpt-layout.js")


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_planning_profile_is_strictly_read_only():
    instructions = _mode_instructions("planning")

    assert CHAT_PROFILES["planning"] == "DevPilot Planejador"
    assert "somente leitura" in instructions
    assert "NUNCA crie, aprove, execute" in instructions
    assert "nenhuma execução ocorreu" in instructions


def test_build_profile_stages_approved_execution():
    instructions = _mode_instructions("build")

    assert CHAT_PROFILES["build"] == "DevPilot Construtor"
    assert "tarefa real de construção" in instructions
    assert "auditoria" in instructions
    assert "aprovação obrigatória" in instructions


def test_text_chat_allows_rich_detailed_answers():
    instructions = _mode_instructions("planning", "chat")

    assert "Não imponha limite artificial de uma a quatro frases" in instructions
    assert "Use Markdown" in instructions
    assert "blocos de código" in instructions
    assert "Preserve quebras de linha" in instructions


def test_voice_style_remains_concise_and_spoken():
    instructions = _mode_instructions("planning", "voice")

    assert "A resposta será falada em voz alta" in instructions
    assert "evite Markdown" in instructions
    assert "uma e quatro frases" in instructions


def test_chat_mode_and_response_style_are_validated_in_every_request():
    planning = DevPilotChatRequest(transcript="Analise o projeto", mode="planning")
    build = DevPilotChatRequest(transcript="Implemente a correção", mode="build", response_style="voice")

    assert planning.mode == "planning"
    assert planning.response_style == "chat"
    assert build.mode == "build"
    assert build.response_style == "voice"

    with pytest.raises(ValidationError):
        DevPilotChatRequest(transcript="Teste", mode="unsafe")
    with pytest.raises(ValidationError):
        DevPilotChatRequest(transcript="Teste", response_style="unsafe")


def test_chat_accepts_larger_technical_prompts():
    request = DevPilotChatRequest(transcript="x" * 12000)
    assert len(request.transcript) == 12000

    with pytest.raises(ValidationError):
        DevPilotChatRequest(transcript="x" * 12001)


def test_chat_ui_has_two_explicit_mode_buttons_and_persists_selection():
    source = _source()

    assert "devpilot-chat-mode" in source
    assert 'data-chat-mode="planning"' in source
    assert 'data-chat-mode="build"' in source
    assert "Planejamento" in source
    assert "Construir" in source
    assert "localStorage.setItem(CHAT_MODE_STORAGE_KEY" in source


def test_chat_sends_mode_project_history_and_response_style():
    source = _source()

    assert "api('/chat'" in source
    assert "project_id: projectId || null" in source
    assert "history: requestHistory" in source
    assert "mode," in source
    assert "response_style: responseStyle" in source
    assert "devpilot:build-task-staged" in source


def test_chat_preserves_conversation_and_rich_content():
    source = _source()

    assert "sessionStorage.setItem(sessionKey()" in source
    assert "renderRichText" in source
    assert "Copiar código" in source
    assert "Regenerar" in source
    assert "Nova conversa" in source
    assert "AbortController" in source
    assert "MAX_STORED_TURNS = 40" in source
    assert ".replace(/\\r\\n?/g, '\\n').trim()" in source


def test_chat_does_not_clear_history_when_modal_closes():
    source = _source()
    close_handler = source.split("modal.addEventListener('close'", 1)[1]

    assert "saveHistory();" in close_handler
    assert "history = [];" not in close_handler.split("});", 1)[0]


def test_planning_is_the_safe_default():
    source = _source()

    assert "localStorage.setItem(CHAT_MODE_STORAGE_KEY, 'planning')" in source
    assert "normalizeMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY) || 'planning')" in source
