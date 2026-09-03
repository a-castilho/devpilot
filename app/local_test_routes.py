from __future__ import annotations

import socket
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.game_rule_routes import router as game_rule_router
from app.pipeline_repair_routes import router as pipeline_repair_router
from app.security import Principal, Role, require_roles
from app.services.audit import record
from app.version import __version__


local_test_router = APIRouter(prefix="/api/admin/local-test", tags=["admin-local-test"])
manage_local_test = require_roles(Role.SUPER_ADMIN)
STATIC = Path(__file__).parent / "static"
_PROBE_TIMEOUT = 3.0

MANUAL_MOBILE_CHECKLIST = [
    "Nenhum texto cortado",
    "Botão Gerar URL totalmente visível",
    "Página com scroll vertical",
    "Menu inferior não cobre o botão",
    "Popup/IA não cobre a entrega final",
    "URL pode ser tocada",
    "Rotação/reload não perde o estado da missão",
]


def _private_non_loopback(value: str | None) -> str:
    candidate = str(value or "").split("%", 1)[0].strip()
    try:
        address = ip_address(candidate)
    except ValueError:
        return ""
    if address.is_private and not address.is_loopback:
        return candidate
    return ""


def _detect_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return _private_non_loopback(sock.getsockname()[0])
    except OSError:
        return ""
    finally:
        sock.close()


def _mobile_url(request: Request) -> tuple[str, str]:
    request_host = _private_non_loopback(request.url.hostname)
    host = request_host or _detect_lan_ip() or "127.0.0.1"
    scheme = "https" if request.url.scheme == "https" else "http"
    port = request.url.port
    if port is None:
        port = 443 if scheme == "https" else 80
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    authority = host if default_port else f"{host}:{port}"
    return host, f"{scheme}://{authority}"


def _probe_health(base_url: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/health"
    try:
        response = httpx.get(url, timeout=_PROBE_TIMEOUT, follow_redirects=False)
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    except (httpx.HTTPError, ValueError):
        return {
            "id": "lan_api",
            "label": "API acessível pela rede local",
            "ok": False,
            "detail": f"Sem resposta válida em {url}",
        }
    ok = response.status_code == 200 and payload.get("status") == "ok" and payload.get("service") == "devpilot"
    return {
        "id": "lan_api",
        "label": "API acessível pela rede local",
        "ok": ok,
        "detail": f"HTTP {response.status_code} · {payload.get('service') or 'resposta recebida'}",
    }


def _source_checks() -> list[dict[str, Any]]:
    requirements = [
        ("mobile_scroll", "Scroll mobile habilitado", STATIC / "mobile-scroll-unlock.css", None),
        ("mission_state", "Estado da missão persistente", STATIC / "build-game.js", ("MISSION_KEY", "localStorage")),
        ("delivery_button", "Entrega final/Gerar URL instalada", STATIC / "build-game-url-bonus.js", ("data-game-url-action", "missionDelivered")),
    ]
    checks: list[dict[str, Any]] = []
    for check_id, label, path, needles in requirements:
        ok = path.is_file()
        detail = f"{path.name} encontrado" if ok else f"{path.name} ausente"
        if ok and needles:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                content = ""
            ok = all(needle in content for needle in needles)
            detail = f"{path.name} contém os controles esperados" if ok else f"{path.name} incompleto"
        checks.append({"id": check_id, "label": label, "ok": ok, "detail": detail})
    return checks


@local_test_router.get("")
def local_test_context(
    request: Request,
    principal: Principal = Depends(manage_local_test),
):
    host, mobile_url = _mobile_url(request)
    return {
        "authorized": True,
        "role": principal.role.value,
        "version": __version__,
        "linux_ip": host,
        "mobile_url": mobile_url,
        "manual_checklist": MANUAL_MOBILE_CHECKLIST,
    }


@local_test_router.post("/run")
def run_local_test(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_local_test),
):
    host, mobile_url = _mobile_url(request)
    checks = [
        {
            "id": "authorization",
            "label": "Autorização Super Admin",
            "ok": principal.role is Role.SUPER_ADMIN,
            "detail": f"Sessão autenticada como {principal.role.value}",
        },
        {
            "id": "local_api",
            "label": "API local do DevPilot ativa",
            "ok": True,
            "detail": f"DevPilot {__version__} executando este diagnóstico",
        },
        _probe_health(mobile_url),
        *_source_checks(),
    ]
    passed = sum(1 for item in checks if item["ok"])
    result = {
        "authorized": True,
        "role": principal.role.value,
        "version": __version__,
        "linux_ip": host,
        "mobile_url": mobile_url,
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "checks": checks,
        "manual_checklist": MANUAL_MOBILE_CHECKLIST,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="local_test.run",
        outcome="success" if result["ok"] else "warning",
        details={"passed": passed, "total": len(checks), "linux_ip": host, "mobile_url": mobile_url},
    )
    db.commit()
    return result


router = APIRouter()
router.include_router(local_test_router)
router.include_router(game_rule_router)
router.include_router(pipeline_repair_router)
