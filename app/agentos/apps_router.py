from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.app_connections import AppConnectionConflict
from app.agentos.container import build_agentos_services
from app.agentos.contracts import KnownAppsConnect
from app.db import get_db
from app.models import Workspace
from app.security import require_access


router = APIRouter(prefix="/api/agentos/apps", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


@router.get("/profiles")
def list_known_app_profiles():
    return build_agentos_services_for_profiles()


def build_agentos_services_for_profiles():
    # Profile definitions are framework-free and do not require a DB session.
    from app.agentos.application.app_connections import KnownAppConnectionService

    return KnownAppConnectionService.profiles()


@router.get("/connections")
def list_app_connections(db: Session = Depends(get_db)):
    ws = _workspace(db)
    items = build_agentos_services(db).app_connections.list_connections(workspace_id=ws.id)
    return [
        {
            "id": item.id,
            "project_id": item.project_id,
            "profile_key": item.profile_key,
            "profile_version": item.profile_version,
            "memory_version": item.memory_version,
        }
        for item in items
    ]


@router.post("/connect-known")
def connect_known_apps(payload: KnownAppsConnect, db: Session = Depends(get_db)):
    ws = _workspace(db)
    try:
        items = build_agentos_services(db).app_connections.connect(
            workspace_id=ws.id,
            keys=payload.keys or None,
            seed_memory=payload.seed_memory,
        )
    except AppConnectionConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {"connected": len(items), "apps": items}
