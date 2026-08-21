from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.career_models import CareerProfile
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

router = APIRouter(prefix="/api/career", tags=["career"])
CAREER_WRITERS = require_roles(Role.OWNER, Role.ADMIN, Role.ANALYST)


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
    return db.scalar(
        select(CareerProfile).where(
            CareerProfile.user_id == principal.user_id,
            CareerProfile.workspace_id == principal.workspace_id,
        )
    )


def _profile_or_404(db: Session, principal: Principal) -> CareerProfile:
    item = _profile_or_none(db, principal)
    if not item:
        raise HTTPException(404, "Importe um currículo antes de usar o Career Sync")
    return item


def _view(item: CareerProfile) -> dict[str, Any]:
    desired = loads_profile(item.profile_json)
    baseline = loads_profile(item.linkedin_baseline_json)
    approved = loads_profile(item.approved_profile_json)
    return {
        "id": item.id,
        "source_filename": item.source_filename,
        "source_sha256": item.source_sha256,
        "profile": desired,
        "linkedin_baseline": baseline,
        "changes": profile_diff(baseline, desired),
        "approved": bool(item.approved_at and approved),
        "approved_at": item.approved_at,
        "updated_at": item.updated_at,
        "linkedin": {
            "mode": "approval_and_export",
            "direct_profile_edit": False,
            "reason": (
                "A API de edição de perfil do LinkedIn exige acesso aprovado. "
                "O DevPilot não usa automação de navegador; após aprovação oficial, "
                "um adapter de publicação pode consumir o mesmo perfil aprovado."
            ),
        },
    }


@router.get("")
def get_career_profile(
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    item = _profile_or_none(db, principal)
    if not item:
        return {
            "profile": None,
            "changes": [],
            "approved": False,
            "linkedin": {"mode": "approval_and_export", "direct_profile_edit": False},
        }
    return _view(item)


@router.post("/cv/import")
async def import_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(CAREER_WRITERS),
):
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
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="career.cv.imported",
        details={
            "filename": item.source_filename,
            "sha256": digest,
            "experience_items": len(profile.get("experience", [])),
            "skills": len(profile.get("skills", [])),
        },
    )
    db.commit()
    db.refresh(item)
    return _view(item)


@router.put("/linkedin/baseline")
def save_linkedin_baseline(
    payload: LinkedInBaseline,
    db: Session = Depends(get_db),
    principal: Principal = Depends(CAREER_WRITERS),
):
    item = _profile_or_404(db, principal)
    item.linkedin_baseline_json = dumps_profile(payload.model_dump())
    item.approved_profile_json = "{}"
    item.approved_at = None
    item.updated_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="career.linkedin.baseline_updated",
        details={"source_sha256": item.source_sha256},
    )
    db.commit()
    db.refresh(item)
    return _view(item)


@router.post("/linkedin/approve")
def approve_linkedin_sync(
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(CAREER_WRITERS),
):
    item = _profile_or_404(db, principal)
    if payload.expected_source_sha256 and payload.expected_source_sha256 != item.source_sha256:
        raise HTTPException(409, "O currículo mudou desde a revisão. Gere o preview novamente")
    desired = loads_profile(item.profile_json)
    if not desired:
        raise HTTPException(409, "Perfil canônico vazio")
    item.approved_profile_json = dumps_profile(desired)
    item.approved_at = datetime.now(timezone.utc)
    item.updated_at = item.approved_at
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="career.linkedin.sync_approved",
        details={
            "source_sha256": item.source_sha256,
            "changes": len(profile_diff(loads_profile(item.linkedin_baseline_json), desired)),
        },
    )
    db.commit()
    db.refresh(item)
    return _view(item)


@router.get("/linkedin/export")
def export_linkedin_package(
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    item = _profile_or_404(db, principal)
    approved = loads_profile(item.approved_profile_json)
    if not item.approved_at or not approved:
        raise HTTPException(409, "Aprove o preview antes de exportar")
    baseline = loads_profile(item.linkedin_baseline_json)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc),
        "source": {"filename": item.source_filename, "sha256": item.source_sha256},
        "changes": profile_diff(baseline, approved),
        "copy_package": copy_package(approved),
        "profile": approved,
        "publication": {
            "status": "approved_for_manual_or_official_api_sync",
            "direct_profile_edit": False,
            "safety": "browser_automation_disabled",
        },
    }
