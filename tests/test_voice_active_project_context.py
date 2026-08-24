from pathlib import Path


SCRIPT = Path("app/static/voice-chatgpt-layout.js")


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_voice_chat_persists_and_restores_active_project():
    source = _source()

    assert "devpilot-chat-active-project-id" in source
    assert "restoreActiveProject" in source
    assert "projectSelect.addEventListener('change'" in source
    assert "MutationObserver" in source


def test_voice_chat_sends_active_project_instead_of_reading_transient_select_value():
    source = _source()

    assert "const projectId = activeProjectId();" in source
    assert "project_id: projectId || null" in source
    assert "project_id: projectSelect?.value || null" not in source


def test_voice_and_text_expose_shared_project_context():
    source = _source()

    assert "window.devpilotChatProjectContext" in source
    assert "getProjectId: () => activeProjectId() || null" in source
    assert "setProjectId: (projectId)" in source
    assert "O projeto selecionado no chat é enviado automaticamente" in source
