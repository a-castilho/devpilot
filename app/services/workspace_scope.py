from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Workspace
from app.security import Principal


_AUTH_ERROR = "Invalid or expired access token"


def _workspace_by_id(db: Session, workspace_id: str) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not workspace:
        raise HTTPException(status_code=401, detail=_AUTH_ERROR)
    return workspace


def workspace_for_principal(db: Session, principal: Principal) -> Workspace:
    """Resolve the authenticated principal workspace without implicit fallback.

    Authenticated routes must never infer tenancy from a conventional slug such as
    ``default``. The workspace id embedded in the validated session principal is the
    authoritative tenant boundary.
    """
    workspace_id = str(principal.workspace_id or "").strip()
    if not workspace_id:
        raise HTTPException(status_code=401, detail=_AUTH_ERROR)

    db.info["principal_workspace_id"] = workspace_id
    return _workspace_by_id(db, workspace_id)


def workspace_for_authenticated_session(db: Session) -> Workspace:
    """Resolve tenant scope for legacy authenticated routes from session context.

    ``session_principal`` already writes the validated user id to ``Session.info``.
    Legacy routers can therefore stop resolving the conventional ``default`` slug
    without changing every endpoint signature at once. The first lookup obtains the
    user's workspace id from the database and caches it only for this request-scoped
    SQLAlchemy session. Missing session context fails closed; there is no slug fallback.
    """
    workspace_id = str(db.info.get("principal_workspace_id") or "").strip()
    if not workspace_id:
        user_id = str(db.info.get("principal_user_id") or "").strip()
        if not user_id:
            raise HTTPException(status_code=401, detail=_AUTH_ERROR)
        workspace_id = str(
            db.scalar(
                select(User.workspace_id).where(
                    User.id == user_id,
                    User.active.is_(True),
                )
            )
            or ""
        ).strip()
        if not workspace_id:
            raise HTTPException(status_code=401, detail=_AUTH_ERROR)
        db.info["principal_workspace_id"] = workspace_id

    return _workspace_by_id(db, workspace_id)
