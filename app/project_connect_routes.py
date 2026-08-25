from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import organization_view, sync_organization, workspace
from app.db import get_db
from app.models import Organization
from app.schemas import OrganizationSync
from app.security import require_access, require_super_admin
from app.services.audit import record


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


@router.post("/projects/connect-all")
def connect_all_projects(
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    """Import and link every GitHub repository from every configured organization."""
    ws = workspace(db)
    organizations = db.scalars(
        select(Organization)
        .where(
            Organization.workspace_id == ws.id,
            Organization.provider == "github",
        )
        .order_by(Organization.created_at.asc())
    ).all()

    if not organizations:
        raise HTTPException(
            status_code=409,
            detail="Nenhuma organização GitHub está conectada ao DevPilot.",
        )

    connected = 0
    repositories = 0
    imported_projects = 0
    linked_projects = 0
    failures: list[dict[str, str]] = []
    results: list[dict] = []

    for organization in organizations:
        try:
            result = sync_organization(
                organization.id,
                OrganizationSync(import_projects=True),
                db=db,
                actor=actor,
            )
        except HTTPException as error:
            failures.append(
                {
                    "organization_id": organization.id,
                    "organization": organization.external_login,
                    "error": str(error.detail),
                }
            )
            continue

        connected += 1
        repositories += int(result.get("repositories") or 0)
        imported_projects += int(result.get("imported_projects") or 0)
        linked_projects += int(result.get("linked_projects") or 0)
        results.append(result)

    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="projects.connect_all",
        outcome="success" if not failures else "partial",
        details={
            "organizations_total": len(organizations),
            "organizations_connected": connected,
            "repositories": repositories,
            "imported_projects": imported_projects,
            "linked_projects": linked_projects,
            "failures": failures,
        },
    )
    db.commit()

    return {
        "status": "ready" if not failures else "partial",
        "organizations_total": len(organizations),
        "organizations_connected": connected,
        "repositories": repositories,
        "imported_projects": imported_projects,
        "linked_projects": linked_projects,
        "failures": failures,
        "organizations": [organization_view(db, item) for item in organizations],
        "results": results,
    }
