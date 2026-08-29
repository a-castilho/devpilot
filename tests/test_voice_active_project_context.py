from pathlib import Path


SCRIPT = Path("app/static/voice-chatgpt-layout.js")
AUTOLOAD_SCRIPT = Path("app/static/voice-project-autoload.js")


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _autoload_source() -> str:
    return AUTOLOAD_SCRIPT.read_text(encoding="utf-8")


def test_voice_chat_persists_and_restores_active_project():
    source = _source()
    autoload = _autoload_source()

    assert "devpilot-chat-active-project-id" in source
    assert "restoreActiveProject" in source
    assert "projectSelect.addEventListener('change'" in source
    assert "MutationObserver" not in source
    assert "syncActiveProjectSelection" in autoload
    assert "source: 'voice-project-options-ready'" in autoload
    assert "document.dispatchEvent(new CustomEvent('devpilot:active-project-changed'" in autoload


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
    assert "detail: {project_id: value || null}" in source
    assert "storeActiveProject(value)" in source
    assert "if (previous !== value) switchSession(" in source
    assert "const sessionKey = () =>" in source
