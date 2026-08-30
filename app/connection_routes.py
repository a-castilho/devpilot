from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.connection_models import ProductConnection
from app.db import get_db
from app.models import Project, ProviderCredential
from app.security import Principal, Role, require_roles
from app.services.audit import record


router = APIRouter(prefix="/api/admin/connections", tags=["admin-connections"])
manage_connections = require_roles(Role.SUPER_ADMIN)

_SUPPORTED_PROVIDERS = {"github", "vercel", "render", "neon"}
_ALLOWED_ENVIRONMENTS = {"development", "homologation", "production"}
_ALLOWED_SCOPES = {
    "read",
    "write",
    "deploy",
    "repository:read",
    "repository:write",
    "database:read",
    "database:write",
    "service:read",
    "service:write",
}


class ConnectionCreate(BaseModel):
    source_project_id: str = Field(min_length=1, max_length=36)
    target_kind: Literal["project", "provider"]
    target_ref: str = Field(min_length=1, max_length=120)
    environment: str = Field(default="production", max_length=30)
    scopes: list[str] = Field(min_length=1, max_length=20)
    authorized: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionAuthorization(BaseModel):
    authorized: bool


def _project(db: Session, workspace_id: str, project_id: str) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado neste workspace")
    return project


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized = sorted({scope.strip().lower() for scope in scopes if scope.strip()})
    if not normalized:
        raise HTTPException(status_code=422, detail="Informe ao menos um scope")
    unsupported = sorted(set(normalized) - _ALLOWED_SCOPES)
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail=f"Scopes não suportados: {', '.join(unsupported)}",
        )
    return normalized


def _credential_for_provider(
    db: Session, workspace_id: str, provider: str
) -> ProviderCredential:
    provider = provider.strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=422, detail="Provider não suportado")
    item = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"cloud:{provider}",
            ProviderCredential.label == "cloud-admin",
        )
    )
    if not item:
        raise HTTPException(
            status_code=409,
            detail="Provider ainda não possui credencial configurada no DevPilot",
        )
    if not item.enabled:
        raise HTTPException(status_code=409, detail="Credencial do provider está desativada")
    return item


def _serialize(item: ProductConnection) -> dict[str, Any]:
    try:
        scopes = json.loads(item.scopes or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        scopes = []
    try:
        metadata = json.loads(item.metadata_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    return {
        "id": item.id,
        "source_project_id": item.source_project_id,
        "target_kind": item.target_kind,
        "target_ref": item.target_ref,
        "environment": item.environment,
        "scopes": scopes,
        "metadata": metadata,
        "status": item.status,
        "enabled": item.enabled,
        "authorized": item.authorized,
        "last_error": item.last_error,
        "last_checked_at": item.last_checked_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _get_connection(db: Session, principal: Principal, connection_id: str) -> ProductConnection:
    item = db.scalar(
        select(ProductConnection).where(
            ProductConnection.id == connection_id,
            ProductConnection.workspace_id == principal.workspace_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    return item


@router.get("")
def list_connections(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_connections),
):
    rows = db.scalars(
        select(ProductConnection)
        .where(ProductConnection.workspace_id == principal.workspace_id)
        .order_by(ProductConnection.created_at.desc())
    ).all()
    return [_serialize(row) for row in rows]


@router.post("", status_code=201)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_connections),
):
    _project(db, principal.workspace_id, payload.source_project_id)
    environment = payload.environment.strip().lower()
    if environment not in _ALLOWED_ENVIRONMENTS:
        raise HTTPException(status_code=422, detail="Environment não suportado")
    scopes = _normalize_scopes(payload.scopes)

    credential_id: str | None = None
    target_ref = payload.target_ref.strip().lower() if payload.target_kind == "provider" else payload.target_ref.strip()
    if payload.target_kind == "project":
        target = _project(db, principal.workspace_id, target_ref)
        if target.id == payload.source_project_id:
            raise HTTPException(status_code=422, detail="Um produto não pode conectar a si próprio")
    else:
        credential_id = _credential_for_provider(db, principal.workspace_id, target_ref).id

    item = ProductConnection(
        workspace_id=principal.workspace_id,
        source_project_id=payload.source_project_id,
        target_kind=payload.target_kind,
        target_ref=target_ref,
        provider_credential_id=credential_id,
        environment=environment,
        scopes=json.dumps(scopes, separators=(",", ":")),
        metadata_json=json.dumps(payload.metadata, ensure_ascii=False, separators=(",", ":")),
        authorized=payload.authorized,
        status="active" if payload.authorized else "pending",
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Esta conexão já está cadastrada") from error

    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="connection.created",
        project_id=payload.source_project_id,
        details={
            "connection_id": item.id,
            "target_kind": item.target_kind,
            "target_ref": item.target_ref,
            "environment": item.environment,
            "scopes": scopes,
            "authorized": item.authorized,
        },
    )
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/{connection_id}/authorize")
def authorize_connection(
    connection_id: str,
    payload: ConnectionAuthorization,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_connections),
):
    item = _get_connection(db, principal, connection_id)
    item.authorized = payload.authorized
    item.status = "active" if payload.authorized and item.enabled else "revoked"
    item.last_error = ""
    item.last_checked_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="connection.authorization_changed",
        project_id=item.source_project_id,
        details={"connection_id": item.id, "authorized": item.authorized},
    )
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/{connection_id}/check")
def check_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_connections),
):
    item = _get_connection(db, principal, connection_id)
    error = ""
    if not item.enabled:
        error = "Conexão desativada"
    elif not item.authorized:
        error = "Conexão sem autorização"
    elif item.target_kind == "project":
        try:
            _project(db, principal.workspace_id, item.target_ref)
        except HTTPException:
            error = "Produto de destino não está disponível"
    else:
        try:
            credential = _credential_for_provider(db, principal.workspace_id, item.target_ref)
            if item.provider_credential_id != credential.id:
                item.provider_credential_id = credential.id
        except HTTPException as exc:
            error = str(exc.detail)

    item.last_checked_at = datetime.now(timezone.utc)
    item.last_error = error
    item.status = "degraded" if error else "active"
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="connection.checked",
        outcome="failed" if error else "success",
        project_id=item.source_project_id,
        details={"connection_id": item.id, "target_ref": item.target_ref},
    )
    db.commit()
    db.refresh(item)
    return {"ok": not error, "connection": _serialize(item)}


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_connections),
):
    item = _get_connection(db, principal, connection_id)
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="connection.deleted",
        project_id=item.source_project_id,
        details={"connection_id": item.id, "target_ref": item.target_ref},
    )
    db.delete(item)
    db.commit()
    return None
