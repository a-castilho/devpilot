from pathlib import Path


SOURCE = Path("app/static/linux-game-access.js")


def test_super_admin_output_stays_open_after_session_refresh():
    source = SOURCE.read_text(encoding="utf-8")

    assert "const adminOpenSessions = new Set();" in source
    assert "adminOpenSessions.add(String(sessionId));" in source
    assert "adminOpenSessions.has(sessionId)" in source
    assert "void readSessionOutput(sessionId, article, false);" in source


def test_closed_sessions_are_removed_from_open_output_state():
    source = SOURCE.read_text(encoding="utf-8")

    assert "adminOpenSessions.delete(String(sessionId));" in source
    assert "if (!activeIds.has(sessionId)) adminOpenSessions.delete(sessionId);" in source
