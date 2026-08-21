from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import require_access
from app.telemetry import (
    TelemetryEvent,
    aware,
    default_workspace,
    now_utc,
    parse_payload,
    session_or_404,
    session_view,
)


router = APIRouter(prefix="/api/telemetry", dependencies=[Depends(require_access)])


class PointerEventIn(BaseModel):
    grid_x: int = Field(ge=0, le=19)
    grid_y: int = Field(ge=0, le=19)
    occurred_at: datetime | None = None


class PointerEventBatch(BaseModel):
    events: list[PointerEventIn] = Field(min_length=1, max_length=250)


def clean_pointer(payload: dict[str, Any]) -> dict[str, int]:
    def grid(name: str) -> int:
        try:
            return max(0, min(19, int(payload.get(name, 0))))
        except (TypeError, ValueError):
            return 0

    return {"grid_x": grid("grid_x"), "grid_y": grid("grid_y")}


def timeline_event(row: TelemetryEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "source": row.source,
        "event_type": row.event_type,
        "occurred_at": row.occurred_at,
        "payload": parse_payload(row),
    }


@router.post("/sessions/{session_id}/pointer")
def ingest_pointer_events(
    session_id: str,
    payload: PointerEventBatch,
    db: Session = Depends(get_db),
):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    if item.status != "recording" or aware(item.ends_at) <= now_utc():
        if item.status == "recording":
            item.status = "completed"
            item.stopped_at = item.ends_at
            db.commit()
        raise HTTPException(409, "Telemetry session is not recording")

    for incoming in payload.events:
        clean = clean_pointer(incoming.model_dump())
        db.add(
            TelemetryEvent(
                session_id=item.id,
                source="browser",
                event_type="move",
                occurred_at=incoming.occurred_at or now_utc(),
                fingerprint=f"move:{clean['grid_x']}:{clean['grid_y']}",
                payload=json.dumps(clean, separators=(",", ":")),
            )
        )
    db.commit()
    return {"accepted": len(payload.events)}


@router.get("/sessions/{session_id}/timeline")
def get_session_timeline(
    session_id: str,
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    ws = default_workspace(db)
    item = session_or_404(db, ws.id, session_id)
    rows = db.scalars(
        select(TelemetryEvent)
        .where(TelemetryEvent.session_id == item.id)
        .order_by(TelemetryEvent.occurred_at.asc(), TelemetryEvent.id.asc())
        .limit(limit)
    ).all()
    return {
        "session": session_view(db, item),
        "events": [timeline_event(row) for row in rows],
        "simulation_only": True,
        "privacy": {
            "typed_content_stored": False,
            "terminal_commands_sanitized": True,
            "pointer_coordinates": "coarse_20x20_grid",
        },
    }
