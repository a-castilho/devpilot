from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.local_test_routes import MANUAL_MOBILE_CHECKLIST, _mobile_url, local_test_context, manage_local_test
from app.security import Principal, Role


ROOT = Path(__file__).resolve().parents[1]


def principal(role: Role) -> Principal:
    return Principal(
        user_id="user-1",
        workspace_id="workspace-1",
        email="root@example.com",
        role=role,
    )


def request(host: str = "192.168.3.130:8080") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/admin/local-test",
            "raw_path": b"/api/admin/local-test",
            "query_string": b"",
            "headers": [(b"host", host.encode())],
            "client": ("192.168.3.20", 50000),
            "server": ("192.168.3.130", 8080),
        }
    )


def test_local_test_is_super_admin_only():
    with pytest.raises(HTTPException) as error:
        manage_local_test(principal(Role.ADMIN))
    assert error.value.status_code == 403

    allowed = manage_local_test(principal(Role.SUPER_ADMIN))
    assert allowed.role is Role.SUPER_ADMIN


def test_mobile_url_prefers_private_request_host():
    host, url = _mobile_url(request())
    assert host == "192.168.3.130"
    assert url == "http://192.168.3.130:8080"


def test_context_returns_the_authorized_mobile_checklist():
    result = local_test_context(request(), principal=principal(Role.SUPER_ADMIN))
    assert result["authorized"] is True
    assert result["role"] == "SUPER_ADMIN"
    assert result["mobile_url"] == "http://192.168.3.130:8080"
    assert result["manual_checklist"] == MANUAL_MOBILE_CHECKLIST
    assert "Botão Gerar URL totalmente visível" in result["manual_checklist"]
    assert "Rotação/reload não perde o estado da missão" in result["manual_checklist"]


def test_frontend_is_wired_into_spa_and_has_no_shell_command_input():
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    frontend = (ROOT / "app" / "static" / "super-admin-local-test.js").read_text(encoding="utf-8")
    backend = (ROOT / "app" / "local_test_routes.py").read_text(encoding="utf-8")

    assert "local_test_router" in main
    assert "/assets/super-admin-local-test.js" in main
    assert "Acesso exclusivo do Super Admin" in frontend
    assert "Executar teste agora" in frontend
    assert "subprocess" not in backend
    assert "shell=True" not in backend
    assert "manage_local_test = require_roles(Role.SUPER_ADMIN)" in backend
