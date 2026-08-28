from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, ProviderCredential, Workspace
from app.security import Principal, Role, require_access, require_roles, require_super_admin, session_principal
from app.services.audit import record
from app.services.product_delivery import (
    LEGACY_CREDENTIAL_LABEL,
    LEGACY_PROVIDER_PREFIX,
    PROVIDERS,
    connection,
    delivery_alerts,
    initial_delivery,
    public_delivery_state,
    run_delivery,
    save_delivery,
    verify,
)
from app.services.vault import Vault


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


class ProviderCredentialInput(BaseModel):
    token: str = Field(min_length=8, max_length=10_000)
    account_id: str = Field(default="", max_length=200)


def operator(
    principal: Principal = Depends(require_roles(Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN)),
) -> Principal:
    return principal


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def project_or_404(db: Session, project_id: str) -> Project:
    ws = workspace(db)
    item = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == ws.id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return item


def legacy_credential_row(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{LEGACY_PROVIDER_PREFIX}{provider}",
            ProviderCredential.label == LEGACY_CREDENTIAL_LABEL,
        )
    )


@router.get("/delivery/providers")
def provider_status(
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    return [
        {
            "provider": provider,
            "configured": connection(db, ws.id, provider) is not None,
            "account_id": (connection(db, ws.id, provider) or ("", ""))[1],
        }
        for provider in PROVIDERS
    ]


@router.put("/delivery/providers/{provider}")
def configure_provider(
    provider: str,
    payload: ProviderCredentialInput,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    """Legacy compatibility endpoint. New credentials should be managed in Super Admin > Clouds."""
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Provedor não suportado.")
    ws = workspace(db)
    item = legacy_credential_row(db, ws.id, provider)
    if not item:
        item = ProviderCredential(
            workspace_id=ws.id,
            provider=f"{LEGACY_PROVIDER_PREFIX}{provider}",
            label=LEGACY_CREDENTIAL_LABEL,
            encrypted_secret="",
            models="[]",
        )
        db.add(item)
    item.encrypted_secret = Vault().encrypt(
        json.dumps(
            {"token": payload.token, "account_id": payload.account_id.strip()},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    item.enabled = True
    item.models = "[]"
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="delivery.provider_configured",
        details={"provider": provider, "has_account_id": bool(payload.account_id.strip())},
    )
    db.commit()
    return {"provider": provider, "configured": True, "account_id": payload.account_id.strip()}


@router.get("/delivery/alerts")
def admin_delivery_alerts(
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    return delivery_alerts(db, ws.id)


@router.get("/projects/{project_id}/delivery")
def delivery_status(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    project = project_or_404(db, project_id)
    return public_delivery_state(
        initial_delivery(project),
        super_admin=principal.role is Role.SUPER_ADMIN,
    )


@router.post("/projects/{project_id}/delivery/start")
def delivery_start(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(operator),
):
    project = project_or_404(db, project_id)
    state = run_delivery(db, project, principal.actor)
    return public_delivery_state(state, super_admin=principal.role is Role.SUPER_ADMIN)


@router.post("/projects/{project_id}/delivery/retry")
def delivery_retry(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(operator),
):
    project = project_or_404(db, project_id)
    state = initial_delivery(project)
    state["automatic"] = True
    state["admin_attention"] = False
    state["next_retry_at"] = datetime.now(timezone.utc).isoformat()
    save_delivery(db, project, state)
    result = run_delivery(db, project, principal.actor)
    return public_delivery_state(result, super_admin=principal.role is Role.SUPER_ADMIN)


@router.post("/projects/{project_id}/delivery/verify")
def delivery_verify(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(operator),
):
    project = project_or_404(db, project_id)
    state = initial_delivery(project)
    result = verify(state)
    state.update(result)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    if state["status"] == "ready":
        state["next_retry_at"] = ""
        state["admin_attention"] = False
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="project.delivery_verified",
        outcome="success" if state["status"] == "ready" else "pending",
        details={"status": state["status"]},
    )
    save_delivery(db, project, state)
    return public_delivery_state(state, super_admin=principal.role is Role.SUPER_ADMIN)
