from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.career_models import CareerProfile, LinkedInConnection, LinkedInOAuthState
from app.config import get_settings
from app.db import get_db
from app.security import Principal, Role, require_roles, session_principal
from app.services.audit import record
from app.services.career_sync import (
    copy_package,
    dumps_profile,
    extract_resume_text,
    loads_profile,
    parse_resume,
    profile_diff,
    source_sha256,
)
from app.services.linkedin_oauth import (
    LinkedInOAuthError,
    authorization_url,
    connection_capabilities,
    create_oauth_state,
    exchange_code,
    fetch_userinfo,
    hash_binding,
    new_browser_binding,
    new_oauth_nonce,
    oauth_configured,
    verify_oauth_state,
)
from app.services.vault import Vault

router = APIRouter(prefix="/api/career", tags=["career"])
CAREER_WRITERS = require_roles(Role.OWNER, Role.ADMIN, Role.ANALYST)
LINKEDIN_OAUTH_COOKIE = "devpilot_linkedin_oauth"
LINKEDIN_OAUTH_COOKIE_PATH = "/api/career/linkedin/oauth/callback"


class LinkedInBaseline(BaseModel):
    headline: str = ""
    about: str = ""
    experience: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    expected_source_sha256: str | None = None


def _profile_or_none(db: Session, principal: Principal) -> CareerProfile | None:
    return db.scalar(select(CareerProfile).where(CareerProfile.user_id == principal.user_id, CareerProfile.workspace_id == principal.workspace_id))


def _profile_or_404(db: Session, principal: Principal) -> CareerProfile:
    item = _profile_or_none(db, principal)
    if not item:
        raise HTTPException(404, "Importe um currículo antes de usar o Career Sync")
    return item


def _connection_or_none(db: Session, *, workspace_id: str, user_id: str) -> LinkedInConnection | None:
    return db.scalar(select(LinkedInConnection).where(LinkedInConnection.user_id == user_id, LinkedInConnection.workspace_id == workspace_id))


def _connection_view(connection: LinkedInConnection | None) -> dict[str, Any]:
    if not connection:
        return {"configured": oauth_configured(), "connected": False, "direct_profile_edit": False, "capabilities": {"oauth_connected": False, "identity_read": False, "profile_write": False}}
    capabilities = connection_capabilities(connection.scopes)
    return {"configured": oauth_configured(), "connected": True, "member_id": connection.member_id, "display_name": connection.display_name, "email": connection.email, "scopes": connection.scopes.split(), "expires_at": connection.expires_at, "direct_profile_edit": bool(capabilities["profile_write"]), "capabilities": capabilities}


def _view(item: CareerProfile, connection: LinkedInConnection | None = None) -> dict[str, Any]:
    desired = loads_profile(item.profile_json)
    baseline = loads_profile(item.linkedin_baseline_json)
    approved = loads_profile(item.approved_profile_json)
    linkedin = _connection_view(connection)
    linkedin.update({"mode": "oauth_approval_and_export", "reason": "OAuth oficial disponível. Publicação direta só é habilitada quando o LinkedIn conceder permissões de escrita compatíveis ao aplicativo."})
    return {"id": item.id, "source_filename": item.source_filename, "source_sha256": item.source_sha256, "profile": desired, "linkedin_baseline": baseline, "changes": profile_diff(baseline, desired), "approved": bool(item.approved_at and approved), "approved_at": item.approved_at, "updated_at": item.updated_at, "linkedin": linkedin}


def _view_for_principal(db: Session, principal: Principal, item: CareerProfile) -> dict[str, Any]:
    return _view(item, _connection_or_none(db, workspace_id=principal.workspace_id, user_id=principal.user_id))


def _redirect_uri(request: Request) -> str:
    configured = get_settings().linkedin_redirect_uri.strip()
    return configured or str(request.url_for("linkedin_oauth_callback"))


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.get("")
def get_career_profile(db: Session = Depends(get_db), principal: Principal = Depends(session_principal)):
    item = _profile_or_none(db, principal)
    connection = _connection_or_none(db, workspace_id=principal.workspace_id, user_id=principal.user_id)
    if not item:
        return {"profile": None, "changes": [], "approved": False, "linkedin": _connection_view(connection)}
    return _view(item, connection)


@router.post("/cv/import")
async def import_cv(file: UploadFile = File(...), db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    content = await file.read()
    try:
        text = extract_resume_text(file.filename or "curriculo.docx", content)
        profile = parse_resume(text)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    digest = source_sha256(content)
    item = _profile_or_none(db, principal)
    if not item:
        item = CareerProfile(workspace_id=principal.workspace_id, user_id=principal.user_id)
        db.add(item)
    item.source_filename = file.filename or "curriculo.docx"
    item.source_sha256 = digest
    item.profile_json = dumps_profile(profile)
    item.approved_profile_json = "{}"
    item.approved_at = None
    item.updated_at = datetime.now(timezone.utc)
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="career.cv.imported", details={"filename": item.source_filename, "sha256": digest, "experience_items": len(profile.get("experience", [])), "skills": len(profile.get("skills", []))})
    db.commit(); db.refresh(item)
    return _view_for_principal(db, principal, item)


@router.put("/linkedin/baseline")
def save_linkedin_baseline(payload: LinkedInBaseline, db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    item = _profile_or_404(db, principal)
    item.linkedin_baseline_json = dumps_profile(payload.model_dump())
    item.approved_profile_json = "{}"; item.approved_at = None; item.updated_at = datetime.now(timezone.utc)
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="career.linkedin.baseline_updated", details={"source_sha256": item.source_sha256})
    db.commit(); db.refresh(item)
    return _view_for_principal(db, principal, item)


@router.post("/linkedin/approve")
def approve_linkedin_sync(payload: ApprovalRequest, db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    item = _profile_or_404(db, principal)
    if payload.expected_source_sha256 and payload.expected_source_sha256 != item.source_sha256:
        raise HTTPException(409, "O currículo mudou desde a revisão. Gere o preview novamente")
    desired = loads_profile(item.profile_json)
    if not desired:
        raise HTTPException(409, "Perfil canônico vazio")
    item.approved_profile_json = dumps_profile(desired); item.approved_at = datetime.now(timezone.utc); item.updated_at = item.approved_at
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="career.linkedin.sync_approved", details={"source_sha256": item.source_sha256, "changes": len(profile_diff(loads_profile(item.linkedin_baseline_json), desired))})
    db.commit(); db.refresh(item)
    return _view_for_principal(db, principal, item)


@router.get("/linkedin/export")
def export_linkedin_package(db: Session = Depends(get_db), principal: Principal = Depends(session_principal)):
    item = _profile_or_404(db, principal)
    approved = loads_profile(item.approved_profile_json)
    if not item.approved_at or not approved:
        raise HTTPException(409, "Aprove o preview antes de exportar")
    baseline = loads_profile(item.linkedin_baseline_json)
    connection = _connection_or_none(db, workspace_id=principal.workspace_id, user_id=principal.user_id)
    capabilities = connection_capabilities(connection.scopes) if connection else {"oauth_connected": False, "identity_read": False, "profile_write": False}
    return {"schema_version": 2, "generated_at": datetime.now(timezone.utc), "source": {"filename": item.source_filename, "sha256": item.source_sha256}, "changes": profile_diff(baseline, approved), "copy_package": copy_package(approved), "profile": approved, "publication": {"status": "approved_for_official_api_or_manual_sync", "direct_profile_edit": bool(capabilities.get("profile_write")), "oauth_connected": bool(capabilities.get("oauth_connected")), "safety": "official_api_only_browser_automation_disabled"}}


@router.get("/linkedin/oauth/start")
def start_linkedin_oauth(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    settings = get_settings()
    binding = new_browser_binding()
    nonce = new_oauth_nonce()
    state = create_oauth_state(workspace_id=principal.workspace_id, user_id=principal.user_id, nonce=nonce)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.linkedin_oauth_state_ttl_seconds)
    db.add(LinkedInOAuthState(workspace_id=principal.workspace_id, user_id=principal.user_id, nonce_hash=hash_binding(nonce), browser_binding_hash=hash_binding(binding), expires_at=expires_at))
    try:
        url = authorization_url(redirect_uri=_redirect_uri(request), state=state)
    except LinkedInOAuthError as error:
        db.rollback()
        raise HTTPException(503, str(error)) from error
    db.commit()
    response = JSONResponse({"authorization_url": url})
    response.set_cookie(LINKEDIN_OAUTH_COOKIE, binding, max_age=settings.linkedin_oauth_state_ttl_seconds, httponly=True, secure=request.url.scheme == "https", samesite="lax", path=LINKEDIN_OAUTH_COOKIE_PATH)
    return response


@router.get("/linkedin/oauth/callback", name="linkedin_oauth_callback")
async def linkedin_oauth_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = "", db: Session = Depends(get_db)):
    if error:
        response = RedirectResponse("/?linkedin=error", status_code=303)
        response.delete_cookie(LINKEDIN_OAUTH_COOKIE, path=LINKEDIN_OAUTH_COOKIE_PATH)
        return response
    if not code or not state:
        raise HTTPException(400, "Callback OAuth incompleto")
    try:
        identity = verify_oauth_state(state)
    except LinkedInOAuthError as oauth_error:
        raise HTTPException(400, str(oauth_error)) from oauth_error
    workspace_id = str(identity["workspace_id"]); user_id = str(identity["user_id"]); nonce = str(identity["nonce"])
    pending = db.scalar(select(LinkedInOAuthState).where(LinkedInOAuthState.workspace_id == workspace_id, LinkedInOAuthState.user_id == user_id, LinkedInOAuthState.nonce_hash == hash_binding(nonce)))
    browser_binding = request.cookies.get(LINKEDIN_OAUTH_COOKIE, "")
    if not pending or not browser_binding or not hmac.compare_digest(pending.browser_binding_hash, hash_binding(browser_binding)):
        raise HTTPException(400, "Sessão OAuth inválida. Inicie a conexão novamente")
    if _as_utc(pending.expires_at) < datetime.now(timezone.utc):
        db.delete(pending); db.commit()
        raise HTTPException(400, "Sessão OAuth expirada. Inicie a conexão novamente")
    db.delete(pending); db.commit()
    try:
        token = await exchange_code(code=code, redirect_uri=_redirect_uri(request))
        userinfo = await fetch_userinfo(token.access_token)
    except LinkedInOAuthError as oauth_error:
        raise HTTPException(400, str(oauth_error)) from oauth_error
    connection = _connection_or_none(db, workspace_id=workspace_id, user_id=user_id)
    if not connection:
        connection = LinkedInConnection(workspace_id=workspace_id, user_id=user_id); db.add(connection)
    vault = Vault()
    connection.member_id = userinfo["member_id"]; connection.display_name = userinfo["display_name"]; connection.email = userinfo["email"]
    connection.access_token_ciphertext = vault.encrypt(token.access_token)
    connection.refresh_token_ciphertext = vault.encrypt(token.refresh_token) if token.refresh_token else ""
    connection.scopes = token.scopes; connection.expires_at = token.expires_at; connection.updated_at = datetime.now(timezone.utc)
    record(db, workspace_id=workspace_id, actor=f"linkedin-oauth:{user_id}", action="career.linkedin.oauth_connected", details={"member_id": connection.member_id, "scopes": connection.scopes.split(), "expires_at": connection.expires_at.isoformat() if connection.expires_at else None})
    db.commit()
    response = RedirectResponse("/?linkedin=connected", status_code=303)
    response.delete_cookie(LINKEDIN_OAUTH_COOKIE, path=LINKEDIN_OAUTH_COOKIE_PATH)
    return response


@router.delete("/linkedin/oauth")
def disconnect_linkedin(db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    connection = _connection_or_none(db, workspace_id=principal.workspace_id, user_id=principal.user_id)
    if connection:
        member_id = connection.member_id; db.delete(connection)
        record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="career.linkedin.oauth_disconnected", details={"member_id": member_id})
        db.commit()
    return {"connected": False}


@router.post("/linkedin/publish")
def publish_linkedin_profile(db: Session = Depends(get_db), principal: Principal = Depends(CAREER_WRITERS)):
    item = _profile_or_404(db, principal)
    approved = loads_profile(item.approved_profile_json)
    if not item.approved_at or not approved:
        raise HTTPException(409, "Aprove o preview antes de publicar")
    connection = _connection_or_none(db, workspace_id=principal.workspace_id, user_id=principal.user_id)
    if not connection:
        raise HTTPException(409, "Conecte sua conta LinkedIn via OAuth primeiro")
    capabilities = connection_capabilities(connection.scopes)
    if not capabilities["profile_write"]:
        record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="career.linkedin.publish_blocked", details={"reason": "linkedin_write_permission_unavailable", "source_sha256": item.source_sha256})
        db.commit()
        raise HTTPException(409, capabilities["profile_write_reason"])
    raise HTTPException(501, "Adapter de escrita do LinkedIn ainda não habilitado para este produto")
