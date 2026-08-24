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


def test_chat_mode_is_validated_in_every_request():
    planning = DevPilotChatRequest(transcript="Analise o projeto", mode="planning")
    build = DevPilotChatRequest(transcript="Implemente a correção", mode="build")

    assert planning.mode == "planning"
    assert build.mode == "build"

    with pytest.raises(ValidationError):
        DevPilotChatRequest(transcript="Teste", mode="unsafe")


def test_chat_ui_has_two_explicit_mode_buttons_and_persists_selection():
    source = _source()

    assert "devpilot-chat-mode" in source
    assert 'data-chat-mode="planning"' in source
    assert 'data-chat-mode="build"' in source
    assert "Planejamento" in source
    assert "Construir" in source
    assert "localStorage.setItem(CHAT_MODE_STORAGE_KEY" in source


def test_chat_sends_mode_project_and_history_to_mode_aware_endpoint():
    source = _source()

    assert "api('/chat'" in source
    assert "project_id: projectId || null" in source
    assert "history: requestHistory" in source
    assert "mode," in source
    assert "devpilot:build-task-staged" in source


def test_planning_is_the_safe_default():
    source = _source()

    assert "localStorage.setItem(CHAT_MODE_STORAGE_KEY, 'planning')" in source
    assert "normalizeMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY) || 'planning')" in source
