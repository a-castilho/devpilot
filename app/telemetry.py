from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base, get_db
from app.models import Workspace, uid
from app.security import require_access


router = APIRouter(prefix="/api/telemetry", dependencies=[Depends(require_access)])


class TelemetrySession(Base):
    __tablename__ = "telemetry_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="recording", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("telemetry_sessions.id"), index=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fingerprint: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")


class SessionCreate(BaseModel):
    duration_seconds: int = Field(ge=10, le=3600)


class BrowserEventIn(BaseModel):
    event_type: Literal["click", "key", "mouse_move"]
    occurred_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class BrowserEventBatch(BaseModel):
    events: list[BrowserEventIn] = Field(min_length=1, max_length=250)


class TerminalCommandIn(BaseModel):
    command: str = Field(min_length=1, max_length=5000)
    cwd: str = Field(default="", max_length=1000)
    shell: str = Field(default="bash", max_length=30)
    exit_code: int | None = None
    occurred_at: datetime | None = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def default_workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def redact_command(command: str) -> str:
    """Remove common credentials before a terminal command is persisted."""
    value = command.strip()[:5000]
    patterns = (
        (r"(?i)(authorization\s*:\s*bearer\s+)[^\s'\"]+", r"\1***"),
        (r"(?i)(--(?:password|passwd|token|api[-_]?key|secret)(?:=|\s+))[^\s'\"]+", r"\1***"),
        (r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY)[A-Z0-9_]*)=([^\s]+)", r"\1=***"),
        (r"\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{12,})\b", "***"),
        (r"(https?://)[^/@\s:]+:[^/@\s]+@", r"\1***:***@"),
    )
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    return value


def sanitize_cwd(cwd: str) -> str:
    value = re.sub(r"^/home/[^/]+", "~", cwd.strip())
    return value[:500]


def normalize_command(command: str) -> str:
    value = re.sub(r"\s+", " ", redact_command(command)).strip()
    value = re.sub(r"\b[0-9a-f]{12,40}\b", "<id>", value, flags=re.I)
    value = re.sub(r"\b\d{4,}\b", "<n>", value)
    return value[:1000]


def safe_text(value: Any, max_length: int = 40) -> str:
    return re.sub(r"[^a-zA-Z0-9_:+.-]", "", str(value or ""))[:max_length]


def sanitize_browser_payload(event_type: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    def grid(name: str) -> int:
        try:
            return max(0, min(19, int(payload.get(name, 0))))
        except (TypeError, ValueError):
            return 0

    if event_type == "mouse_move":
        clean = {"grid_x": grid("grid_x"), "grid_y": grid("grid_y")}
        return clean, f"mouse_move:{clean['grid_x']}:{clean['grid_y']}"

    if event_type == "click":
        clean = {
            "grid_x": grid("grid_x"),
            "grid_y": grid("grid_y"),
            "tag": safe_text(payload.get("tag"), 20).lower(),
            "role": safe_text(payload.get("role"), 24).lower(),
            "button": safe_text(payload.get("button"), 12).lower(),
        }
        fingerprint = (
            f"click:{clean['tag']}:{clean['role']}:{clean['button']}:"
            f"{clean['grid_x']}:{clean['grid_y']}"
        )
        return clean, fingerprint

    allowed_groups = {"text", "navigation", "editing", "modifier", "function", "shortcut", "other"}
    group = str(payload.get("group", "other"))
    if group not in allowed_groups:
        group = "other"
    shortcut = safe_text(payload.get("shortcut"), 32).lower()
    clean = {
        "group": group,
        "ctrl": bool(payload.get("ctrl")),
        "alt": bool(payload.get("alt")),
        "shift": bool(payload.get("shift")),
        "meta": bool(payload.get("meta")),
        "repeat": bool(payload.get("repeat")),
        "shortcut": shortcut,
    }
    modifiers = "".join(k for k, enabled in (("c", clean["ctrl"]), ("a", clean["alt"]), ("s", clean["shift"]), ("m", clean["meta"])) if enabled)
    return clean, f"key:{group}:{shortcut}:{modifiers}"


def expire_sessions(db: Session, workspace_id: str) -> bool:
    current = now_utc()
    changed = False
    sessions = db.scalars(
        select(TelemetrySession).where(
            TelemetrySession.workspace_id == workspace_id,
            TelemetrySession.status == "recording",
        )
    ).all()
    for item in sessions:
        if aware(item.ends_at) <= current:
            item.status = "completed"
            item.stopped_at = item.ends_at
            changed = True
    return changed


def active_session(db: Session, workspace_id: str) -> TelemetrySession | None:
    return db.scalars(
        select(TelemetrySession)
        .where(
            TelemetrySession.workspace_id == workspace_id,
            TelemetrySession.status == "recording",
        )
        .order_by(TelemetrySession.started_at.desc())
    ).first()


def session_or_404(db: Session, workspace_id: str, session_id: str) -> TelemetrySession:
    item = db.scalar(
        select(TelemetrySession).where(
            TelemetrySession.id == session_id,
            TelemetrySession.workspace_id == workspace_id,
        )
    )
    if not item:
        raise HTTPException(404, "Telemetry session not found")
    return item


def parse_payload(row: TelemetryEvent) -> dict[str, Any]:
    try:
        data = json.loads(row.payload or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def build_analysis(rows: list[TelemetryEvent]) -> dict[str, Any]:
    commands: list[str] = []
    click_counter: Counter[str] = Counter()
    shortcut_counter: Counter[str] = Counter()
    key_events = 0
    click_events = 0

    for row in rows:
        payload = parse_payload(row)
        if row.source == "terminal" and row.event_type == "command":
            command = normalize_command(str(payload.get("command", "")))
            if command:
                commands.append(command)
        elif row.source == "browser" and row.event_type == "click":
            click_events += 1
            click_counter[row.fingerprint] += 1
        elif row.source == "browser" and row.event_type == "key":
            key_events += 1
            shortcut = str(payload.get("shortcut", ""))
            if shortcut:
                shortcut_counter[shortcut] += 1

    command_counter = Counter(commands)
    repeated_commands = [
        {"command": command, "occurrences": count}
        for command, count in command_counter.most_common(8)
        if count >= 2
    ]

    sequence_counter: Counter[tuple[str, ...]] = Counter()
    for size in (4, 3, 2):
        for index in range(0, max(0, len(commands) - size + 1)):
            sequence_counter[tuple(commands[index:index + size])] += 1
    repeated_sequences = [
        {"commands": list(sequence), "occurrences": count, "length": len(sequence)}
        for sequence, count in sorted(
            sequence_counter.items(),
            key=lambda item: (item[1] * len(item[0]), item[1], len(item[0])),
            reverse=True,
        )
        if count >= 2
    ][:5]

    repeated_clicks = [
        {"fingerprint": fingerprint, "occurrences": count}
        for fingerprint, count in click_counter.most_common(8)
        if count >= 2
    ]
    repeated_shortcuts = [
        {"shortcut": shortcut, "occurrences": count}
        for shortcut, count in shortcut_counter.most_common(8)
        if count >= 2
    ]

    candidates: list[dict[str, Any]] = []
    for item in repeated_sequences[:3]:
        candidates.append(
            {
                "kind": "terminal_workflow",
                "title": "Sequência de terminal repetida",
                "occurrences": item["occurrences"],
                "confidence": min(0.98, 0.55 + (item["occurrences"] * 0.08) + (item["length"] * 0.04)),
                "proposal": "Transformar a sequência em script/tarefa DevPilot com revisão antes da execução.",
                "evidence": item["commands"],
            }
        )
    for item in repeated_commands[:3]:
        candidates.append(
            {
                "kind": "terminal_command",
                "title": "Comando recorrente",
                "occurrences": item["occurrences"],
                "confidence": min(0.95, 0.5 + item["occurrences"] * 0.08),
                "proposal": "Criar alias, script parametrizado ou ação reutilizável.",
                "evidence": [item["command"]],
            }
        )
    for item in repeated_clicks[:3]:
        candidates.append(
            {
                "kind": "browser_interaction",
                "title": "Clique recorrente na mesma região/controle",
                "occurrences": item["occurrences"],
                "confidence": min(0.9, 0.45 + item["occurrences"] * 0.06),
                "proposal": "Avaliar atalho de interface ou automação da etapa repetitiva.",
                "evidence": [item["fingerprint"]],
            }
        )
    if repeated_sequences and repeated_clicks:
        candidates.insert(
            0,
            {
                "kind": "hybrid_workflow",
                "title": "Fluxo híbrido navegador + terminal",
                "occurrences": min(repeated_sequences[0]["occurrences"], repeated_clicks[0]["occurrences"]),
                "confidence": 0.82,
                "proposal": "Orquestrar interface e terminal como uma única rotina auditável no DevPilot.",
                "evidence": ["terminal", "browser"],
            },
        )

    score = min(
        100,
        (len(repeated_sequences) * 18)
        + (len(repeated_commands) * 10)
        + (len(repeated_clicks) * 7)
        + (len(repeated_shortcuts) * 5),
    )
    return {
        "automation_score": score,
        "summary": {
            "events": len(rows),
            "terminal_commands": len(commands),
            "browser_clicks": click_events,
            "key_events": key_events,
            "repeated_patterns": len(repeated_sequences) + len(repeated_commands) + len(repeated_clicks),
        },
        "patterns": {
            "terminal_sequences": repeated_sequences,
            "terminal_commands": repeated_commands,
            "clicks": repeated_clicks,
            "shortcuts": repeated_shortcuts,
        },
        "candidates": candidates[:8],
        "privacy": {
            "typed_content_stored": False,
            "terminal_secrets_redacted": True,
            "click_coordinates": "coarse_20x20_grid",
        },
    }


def session_view(db: Session, item: TelemetrySession) -> dict[str, Any]:
    counts = dict(
        db.execute(
            select(TelemetryEvent.source, func.count(TelemetryEvent.id))
            .where(TelemetryEvent.session_id == item.id)
            .group_by(TelemetryEvent.source)
        ).all()
    )
    try:
        analysis = json.loads(item.analysis_json or "{}")
    except json.JSONDecodeError:
        analysis = {}
    remaining = max(0, int((aware(item.ends_at) - now_utc()).total_seconds())) if item.status == "recording" else 0
    return {
        "id": item.id,
        "duration_seconds": item.duration_seconds,
        "status": item.status,
        "started_at": item.started_at,
        "ends_at": item.ends_at,
        "stopped_at": item.stopped_at,
        "remaining_seconds": remaining,
        "event_counts": {"browser": counts.get("browser", 0), "terminal": counts.get("terminal", 0)},
        "analysis": analysis,
    }


@router.post("/sessions")
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    if expire_sessions(db, ws.id):
        db.flush()
    if active_session(db, ws.id):
        db.rollback()
        raise HTTPException(409, "A telemetry session is already recording")
    started = now_utc()
    item = TelemetrySession(
        workspace_id=ws.id,
        duration_seconds=payload.duration_seconds,
        status="recording",
        started_at=started,
        ends_at=started + timedelta(seconds=payload.duration_seconds),
        created_at=started,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return session_view(db, item)


@router.get("/sessions/active")
def get_active_session(db: Session = Depends(get_db)):
    ws = default_workspace(db)
    changed = expire_sessions(db, ws.id)
    item = active_session(db, ws.id)
    if changed:
        db.commit()
    return {"active": session_view(db, item) if item else None}


@router.get("/sessions")
def list_sessions(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    ws = default_workspace(db)
    if expire_sessions(db, ws.id):
        db.commit()
    items = db.scalars(
        select(TelemetrySession)
        .where(TelemetrySession.workspace_id == ws.id)
        .order_by(TelemetrySession.started_at.desc())
        .limit(limit)
    ).all()
    return [session_view(db, item) for item in items]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    if item.status == "recording" and aware(item.ends_at) <= now_utc():
        item.status = "completed"
        item.stopped_at = item.ends_at
        db.commit()
    return session_view(db, item)


@router.get("/sessions/{session_id}/events")
def list_session_events(
    session_id: str,
    limit: int = Query(default=2500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Return a sanitized timeline for visual simulation only."""
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    rows = db.scalars(
        select(TelemetryEvent)
        .where(TelemetryEvent.session_id == item.id)
        .order_by(TelemetryEvent.occurred_at, TelemetryEvent.id)
        .limit(limit)
    ).all()
    started_at = aware(item.started_at)
    return {
        "session_id": item.id,
        "truncated": len(rows) == limit,
        "events": [
            {
                "id": row.id,
                "source": row.source,
                "event_type": row.event_type,
                "offset_ms": max(0, int((aware(row.occurred_at) - started_at).total_seconds() * 1000)),
                "payload": parse_payload(row),
            }
            for row in rows
        ],
    }


@router.post("/sessions/{session_id}/events")
def ingest_browser_events(session_id: str, payload: BrowserEventBatch, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    if item.status != "recording" or aware(item.ends_at) <= now_utc():
        if item.status == "recording":
            item.status = "completed"
            item.stopped_at = item.ends_at
            db.commit()
        raise HTTPException(409, "Telemetry session is not recording")

    for incoming in payload.events:
        clean, fingerprint = sanitize_browser_payload(incoming.event_type, incoming.payload)
        occurred_at = incoming.occurred_at or now_utc()
        db.add(
            TelemetryEvent(
                session_id=item.id,
                source="browser",
                event_type=incoming.event_type,
                occurred_at=occurred_at,
                fingerprint=fingerprint,
                payload=json.dumps(clean, separators=(",", ":"), ensure_ascii=False),
            )
        )
    db.commit()
    return {"accepted": len(payload.events)}


@router.post("/terminal/command")
def ingest_terminal_command(payload: TerminalCommandIn, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    changed = expire_sessions(db, ws.id)
    item = active_session(db, ws.id)
    if changed:
        db.commit()
    if not item:
        return {"captured": False, "reason": "no_active_session"}

    command = redact_command(payload.command)
    normalized = normalize_command(command)
    if not normalized:
        return {"captured": False, "reason": "empty_command"}
    fingerprint = "terminal:" + hashlib.sha256(normalized.encode()).hexdigest()[:24]
    clean = {
        "command": command,
        "cwd": sanitize_cwd(payload.cwd),
        "shell": safe_text(payload.shell, 20).lower() or "shell",
        "exit_code": payload.exit_code,
    }
    db.add(
        TelemetryEvent(
            session_id=item.id,
            source="terminal",
            event_type="command",
            occurred_at=payload.occurred_at or now_utc(),
            fingerprint=fingerprint,
            payload=json.dumps(clean, separators=(",", ":"), ensure_ascii=False),
        )
    )
    db.commit()
    return {"captured": True, "session_id": item.id}


@router.post("/sessions/{session_id}/stop")
def stop_session(session_id: str, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    if item.status == "recording":
        item.status = "completed"
        item.stopped_at = now_utc()
        db.commit()
    return session_view(db, item)


@router.post("/sessions/{session_id}/analyze")
def analyze_session(session_id: str, db: Session = Depends(get_db)):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    rows = db.scalars(
        select(TelemetryEvent)
        .where(TelemetryEvent.session_id == item.id)
        .order_by(TelemetryEvent.occurred_at, TelemetryEvent.id)
    ).all()
    analysis = build_analysis(rows)
    item.analysis_json = json.dumps(analysis, separators=(",", ":"), ensure_ascii=False)
    db.commit()
    return analysis
