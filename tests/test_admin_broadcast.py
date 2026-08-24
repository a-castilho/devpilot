from pathlib import Path

import pytest
from fastapi import HTTPException

from app.admin_broadcast_routes import BroadcastRequest, manage_broadcast
from app.main import spa
from app.security import Principal, Role


ROOT = Path(__file__).resolve().parents[1]


def principal(role: Role) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id="workspace-1",
        email="user@example.com",
        role=role,
    )


def test_broadcast_send_is_super_admin_only():
    with pytest.raises(HTTPException) as error:
        manage_broadcast(principal(Role.ADMIN))
    assert error.value.status_code == 403

    allowed = manage_broadcast(principal(Role.SUPER_ADMIN))
    assert allowed.role is Role.SUPER_ADMIN


def test_broadcast_payload_is_bounded_and_has_safe_levels():
    payload = BroadcastRequest(message="Manutenção em 5 minutos", level="warning")
    assert payload.message == "Manutenção em 5 minutos"
    assert payload.level == "warning"

    with pytest.raises(Exception):
        BroadcastRequest(message="x", level="html")


def test_broadcast_frontend_is_loaded_for_every_spa_session():
    rendered = spa("").body.decode("utf-8")
    assert rendered.count("/assets/admin-broadcast.js?v=") == 1


def test_broadcast_ui_has_global_composer_and_authenticated_polling():
    source = (ROOT / "app/static/admin-broadcast.js").read_text(encoding="utf-8")
    backend = (ROOT / "app/admin_broadcast_routes.py").read_text(encoding="utf-8")

    assert "SUPER_ADMIN · TODOS CONECTADOS" in source
    assert "Enviar para todos" in source
    assert "Authorization: `Bearer ${token()}`" in source
    assert "POLL_MS = 2500" in source
    assert "textContent" in source
    assert "require_roles(Role.SUPER_ADMIN)" in backend
    assert "session_principal" in backend
    assert '"scope": "all_connected_users"' in backend
