from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Workspace
from app.security import Principal


def workspace_for_principal(db: Session, principal: Principal) -> Workspace:
    """Resolve the authenticated principal workspace without implicit fallback.

    Authenticated routes must never infer tenancy from a conventional slug such as
    ``default``. The workspace id embedded in the validated session principal is the
    authoritative tenant boundary.
    """
    workspace_id = str(principal.workspace_id or "").strip()
    if not workspace_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not workspace:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    return workspace
