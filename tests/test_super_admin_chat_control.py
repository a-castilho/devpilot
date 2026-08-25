from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
import app.platform_models  # noqa: F401
from app.chat_control_routes import (
    CHAT_CONTROL_KEY,
    DEFAULT_CHAT_ENABLED,
    chat_enabled,
    require_chat_available,
    serialize_chat_control,
)
from app.db import Base
from app.platform_models import PlatformControl
from app import main as main_module


ROOT = Path(__file__).resolve().parents[1]
CONTROL_JS = ROOT / "app" / "static" / "super-admin-chat-control.js"
MAIN_PY = ROOT / "app" / "main.py"


def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_chat_is_off_by_default_and_guard_fails_closed():
    db = session()
    try:
        assert DEFAULT_CHAT_ENABLED is False
        assert chat_enabled(db) is False
        assert serialize_chat_control(None)["enabled"] is False
        with pytest.raises(HTTPException) as exc:
            require_chat_available(db)
        assert exc.value.status_code == 503
        assert "desligado pelo Super Admin" in str(exc.value.detail)
    finally:
        db.close()


def test_stored_super_admin_control_can_enable_chat():
    db = session()
    try:
        item = PlatformControl(
            key=CHAT_CONTROL_KEY,
            enabled=True,
            reason="Diagnóstico concluído",
            updated_by="user:super-admin",
        )
        db.add(item)
        db.commit()
        assert chat_enabled(db) is True
        assert require_chat_available(db) is None
        data = serialize_chat_control(item)
        assert data["enabled"] is True
        assert data["reason"] == "Diagnóstico concluído"
    finally:
        db.close()


def test_main_registers_control_and_backend_chat_guards():
    source = MAIN_PY.read_text(encoding="utf-8")
    assert "app.include_router(chat_control_router)" in source
    assert "app.include_router(chat_mode_router, dependencies=[Depends(require_chat_available)])" in source
    assert "app.include_router(voice_conversation_router, dependencies=[Depends(require_chat_available)])" in source
    assert "import app.platform_models" in source


def test_boot_skips_conversation_assets_when_chat_is_off():
    assert "super-admin-chat-control.js" in main_module._CORE_AUTHENTICATED_SCRIPTS
    assert "voice-chatgpt-layout.js" in main_module._CHAT_AUTHENTICATED_SCRIPTS
    assert "voice-enhanced-ui.js" in main_module._CHAT_AUTHENTICATED_SCRIPTS
    loader = main_module._authenticated_script_loader()
    assert "const chatSources = new Set(" in loader
    assert "boot.skipped.push(src)" in loader
    assert "const chatEnabled = Boolean(window.__devpilotChatControl?.enabled)" in loader
    assert "if (!chatEnabled && chatSources.has(src))" in loader


def test_super_admin_ui_has_on_off_controls_and_fail_closed_state():
    source = CONTROL_JS.read_text(encoding="utf-8")
    assert "enabled: false" in source
    assert "Fail closed" in source
    assert "'/chat/control'" in source
    assert "'/super-admin/chat/control'" in source
    assert "Desligar chat" in source
    assert "Ligar chat" in source
    assert "nav.dataset.superAdmin = 'true'" in source
    assert "#voice-hero" in source
    assert "#voice-dock" in source
    assert "window.location.reload()" in source
