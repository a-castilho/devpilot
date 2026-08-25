from __future__ import annotations

import os
import re
import threading
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.linux_agent import __version__
from app.linux_agent.audit import LinuxAuditError, attest_event, identity_status, linux_identity
from app.linux_agent.auth import AgentAuthError, canonical_target, verify_request
from app.linux_agent.ollama_runtime import OllamaRuntimeError, chat_ollama, ensure_ollama
from app.linux_agent.runtime import SessionManager, SessionNotFound, TerminalUserUnavailable


def agent_secret() -> str:
    return os.environ.get("DEVPILOT_LINUX_AGENT_SECRET", "").strip()


def agent_data_dir() -> Path:
    raw = os.environ.get(
        "DEVPILOT_LINUX_AGENT_DATA_DIR",
        str(Path.home() / ".local" / "share" / "devpilot-linux-agent"),
    )
    return Path(raw).expanduser()


def direct_terminal_user() -> str:
    return os.environ.get("DEVPILOT_LINUX_TERMINAL_USER", "devpilot").strip()


def direct_terminal_launcher() -> str:
    return os.environ.get(
        "DEVPILOT_LINUX_TERMINAL_LAUNCHER",
        "/usr/local/libexec/devpilot-terminal-shell",
    ).strip()


manager = SessionManager(
    agent_data_dir(),
    direct_user=direct_terminal_user(),
    direct_user_launcher=direct_terminal_launcher(),
)


class ReplayGuard:
    def __init__(self, ttl_seconds: int = 90, max_entries: int = 4096) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def accept(self, nonce: str) -> bool:
        now = time.time()
        with self._lock:
            cutoff = now - self.ttl_seconds
            while self._items:
                _, created = next(iter(self._items.items()))
                if created >= cutoff:
                    break
                self._items.popitem(last=False)
            if nonce in self._items:
                return False
            self._items[nonce] = now
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
            return True


replay_guard = ReplayGuard()


async def require_signed_request(
    request: Request,
    timestamp: str | None = Header(default=None, alias="X-DevPilot-Timestamp"),
    nonce: str | None = Header(default=None, alias="X-DevPilot-Nonce"),
    signature: str | None = Header(default=None, alias="X-DevPilot-Signature"),
) -> None:
    secret = agent_secret()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Linux Agent secret não configurado")
    if not timestamp or not nonce or not signature:
        raise HTTPException(status_code=401, detail="Assinatura do DevPilot ausente")

    body = await request.body()
    target = canonical_target(request.url.path, request.url.query)
    try:
        verify_request(
            secret,
            timestamp=timestamp,
            nonce=nonce,
            method=request.method,
            target=target,
            body=body,
            signature=signature,
        )
    except AgentAuthError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error

    if not replay_guard.accept(nonce):
        raise HTTPException(status_code=409, detail="Requisição repetida bloqueada")


class TerminalGitAuth(BaseModel):
    provider: Literal["github"]
    host: Literal["github.com"] = "github.com"
    token: str = Field(min_length=8, max_length=10_000)
    scope: str = Field(default="", max_length=200)


class TerminalCreate(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    workspace_key: str | None = Field(default=None, min_length=16, max_length=64)
    cwd: str | None = Field(default=None, max_length=4096)
    columns: int = Field(default=120, ge=20, le=400)
    rows: int = Field(default=34, ge=5, le=200)
    git_auth: TerminalGitAuth | None = None


class TerminalInput(BaseModel):
    data: str = Field(min_length=1, max_length=100_000)


class TerminalResize(BaseModel):
    columns: int = Field(ge=20, le=400)
    rows: int = Field(ge=5, le=200)


class OllamaChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=12_000)
    input_text: str = Field(min_length=1, max_length=30_000)


class AuditAttestRequest(BaseModel):
    previous_hash: str = Field(default="", max_length=128)
    workspace_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(default="", max_length=100)
    task_id: str = Field(default="", max_length=100)
    run_id: str = Field(default="", max_length=100)
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    outcome: str = Field(default="success", max_length=50)
    details: dict = Field(default_factory=dict)


def user_workspace_dir(workspace_key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{16,64}", workspace_key):
        raise ValueError("Identificador de workspace Linux inválido")
    root = (manager.data_dir / "workspaces").resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    target = (root / workspace_key).resolve()
    if root not in target.parents:
        raise ValueError("Workspace Linux inválido")
    target.mkdir(parents=True, exist_ok=True)
    try:
        target.chmod(0o700)
    except OSError:
        pass
    projects = target / "projects"
    projects.mkdir(exist_ok=True)
    return target


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    manager.close_all()


app = FastAPI(
    title="DevPilot Linux Agent",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health")
def health():
    signed_requests = len(agent_secret()) >= 32
    terminal_user = manager.direct_user_status()
    configured = signed_requests and bool(terminal_user.get("ready"))
    return {
        "status": "ok" if configured else "configuration_required",
        "service": "devpilot-linux-agent",
        "version": __version__,
        "signed_requests": signed_requests,
        "terminal_user": terminal_user,
    }


@app.get("/v1/system", dependencies=[Depends(require_signed_request)])
def system_snapshot():
    snapshot = manager.system_snapshot()
    snapshot["linux_identity"] = linux_identity()
    return snapshot


@app.get("/v1/audit/identity", dependencies=[Depends(require_signed_request)])
def audit_identity():
    try:
        return identity_status()
    except LinuxAuditError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/v1/audit/attest", dependencies=[Depends(require_signed_request)])
def audit_attest(payload: AuditAttestRequest):
    try:
        return attest_event(payload.model_dump())
    except LinuxAuditError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/v1/ollama/ensure", dependencies=[Depends(require_signed_request)])
def ensure_ollama_runtime():
    try:
        return ensure_ollama(manager.data_dir)
    except OllamaRuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/v1/ollama/chat", dependencies=[Depends(require_signed_request)])
def ollama_chat(payload: OllamaChatRequest):
    try:
        return chat_ollama(
            model=payload.model,
            instructions=payload.instructions,
            input_text=payload.input_text,
        )
    except OllamaRuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/v1/terminal/sessions", dependencies=[Depends(require_signed_request)])
def list_terminal_sessions():
    return {"items": manager.list_sessions()}


@app.post("/v1/terminal/sessions", status_code=201, dependencies=[Depends(require_signed_request)])
def create_terminal_session(payload: TerminalCreate):
    try:
        cwd = payload.cwd
        isolated_workspace = bool(payload.workspace_key)
        if payload.workspace_key:
            isolated_root = user_workspace_dir(payload.workspace_key)
            if cwd:
                requested = Path(cwd).expanduser().resolve()
                if requested != isolated_root and isolated_root not in requested.parents:
                    raise ValueError("Diretório fora do workspace Linux do usuário")
            else:
                cwd = str(isolated_root)
        return manager.create(
            actor=payload.actor,
            cwd=cwd,
            columns=payload.columns,
            rows=payload.rows,
            use_direct_user=not isolated_workspace,
            isolated_home=isolated_workspace,
            git_auth=payload.git_auth.model_dump() if payload.git_auth else None,
        )
    except TerminalUserUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get(
    "/v1/terminal/sessions/{session_id}/output",
    dependencies=[Depends(require_signed_request)],
)
def terminal_output(session_id: str, after: int = Query(default=0, ge=0)):
    try:
        return manager.output(session_id, after=after)
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from error


@app.post(
    "/v1/terminal/sessions/{session_id}/input",
    dependencies=[Depends(require_signed_request)],
)
def terminal_input(session_id: str, payload: TerminalInput):
    try:
        return manager.send_input(session_id, payload.data)
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/v1/terminal/sessions/{session_id}/resize",
    dependencies=[Depends(require_signed_request)],
)
def terminal_resize(session_id: str, payload: TerminalResize):
    try:
        return manager.resize(session_id, columns=payload.columns, rows=payload.rows)
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from error


@app.delete(
    "/v1/terminal/sessions/{session_id}",
    dependencies=[Depends(require_signed_request)],
)
def close_terminal_session(session_id: str):
    try:
        return manager.close(session_id)
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from error
