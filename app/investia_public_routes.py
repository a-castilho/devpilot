from __future__ import annotations

from decimal import Decimal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.investia_models import (
    InvestiaCostStatus,
    InvestiaProjectConfig,
    InvestiaProjectCost,
    InvestiaProjectStatus,
)
from app.models import Project, Workspace
from app.rag.runtime import get_rag_service
from app.security import require_super_admin
from app.services.audit import record
from app.services.investia_finance import money


router = APIRouter(prefix="/api/investia", tags=["DevAI Invest Catalog"])


def _workspace(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == "default"))


def _cost_total(db: Session, config_id: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(InvestiaProjectCost.amount), 0)).where(
            InvestiaProjectCost.investia_project_id == config_id,
            InvestiaProjectCost.status == InvestiaCostStatus.approved,
        )
    )
    return money(value or 0)


def _cost_breakdown(db: Session, config_id: str) -> list[dict]:
    rows = db.execute(
        select(InvestiaProjectCost.category, func.sum(InvestiaProjectCost.amount))
        .where(
            InvestiaProjectCost.investia_project_id == config_id,
            InvestiaProjectCost.status == InvestiaCostStatus.approved,
        )
        .group_by(InvestiaProjectCost.category)
        .order_by(InvestiaProjectCost.category)
    ).all()
    return [
        {"category": category.value, "amount": money(amount or 0)}
        for category, amount in rows
    ]


def _publication_status(config: InvestiaProjectConfig) -> str:
    if not config.public_enabled:
        return "not_published"
    if config.status is InvestiaProjectStatus.paused:
        return "paused"
    return "published"


def _accepting_investments(config: InvestiaProjectConfig) -> bool:
    return bool(config.public_enabled and config.status is InvestiaProjectStatus.fundraising)


def _public_view(db: Session, config: InvestiaProjectConfig, project: Project) -> dict:
    return {
        "project_key": config.external_project_key,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "currency": config.currency,
        "funding_target": config.funding_target,
        "minimum_funding": config.minimum_funding,
        "maximum_funding": config.maximum_funding,
        "minimum_investment": config.minimum_investment,
        "maximum_investment_per_user": config.maximum_investment_per_user,
        "investor_share_percentage": config.investor_share_percentage,
        "status": config.status,
        "publication_status": _publication_status(config),
        "accepting_investments": _accepting_investments(config),
        "approved_costs": _cost_total(db, config.id),
        "approved_cost_breakdown": _cost_breakdown(db, config.id),
        "updated_at": config.updated_at,
    }


def _clean_excerpt(value: str, limit: int = 440) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _config_for_admin(
    db: Session,
    project_id: str,
) -> tuple[Workspace, Project, InvestiaProjectConfig]:
    ws = _workspace(db)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == ws.id))
    if not project:
        raise HTTPException(404, "Project not found")
    config = db.scalar(
        select(InvestiaProjectConfig).where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.project_id == project.id,
        )
    )
    if not config:
        raise HTTPException(409, "Configure o projeto antes de publicar no DevAI Invest")
    return ws, project, config


def _publication_view(config: InvestiaProjectConfig, project: Project) -> dict:
    return {
        "project_id": project.id,
        "project_name": project.name,
        "project_key": config.external_project_key,
        "publication_status": _publication_status(config),
        "accepting_investments": _accepting_investments(config),
        "project_status": config.status,
        "public_enabled": config.public_enabled,
    }


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)):
    ws = _workspace(db)
    if not ws:
        return []
    rows = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.public_enabled.is_(True),
        )
        .order_by(InvestiaProjectConfig.created_at.desc())
    ).all()
    return [_public_view(db, config, project) for config, project in rows]


@router.get("/catalog/search")
def search_catalog(
    q: str = Query(default="", max_length=180),
    limit: int = Query(default=6, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Search only explicitly published projects, enriching matches with RAG excerpts.

    The endpoint is intentionally public because it powers the pre-login landing page.
    It never traverses projects without ``public_enabled`` and degrades to project
    metadata when vector retrieval is disabled or unavailable.
    """
    ws = _workspace(db)
    query = str(q or "").strip()
    if not ws:
        return {"query": query, "rag_available": False, "results": []}

    rows = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.public_enabled.is_(True),
        )
        .order_by(InvestiaProjectConfig.updated_at.desc())
        .limit(18)
    ).all()

    rag_available = False
    rag = None
    if query:
        try:
            rag = get_rag_service()
            rag_available = bool(rag.settings.enabled)
        except Exception:
            rag = None

    normalized = query.casefold()
    results: list[dict] = []
    for config, project in rows:
        description = str(project.description or "").strip()
        metadata_match = not query or normalized in f"{project.name} {project.slug} {description}".casefold()
        excerpts: list[dict] = []

        if query and rag is not None and project.organization_id:
            try:
                retrieved = rag.retrieve(
                    organization_id=project.organization_id,
                    project_id=project.id,
                    query=query,
                    diagnostic=False,
                )
                for chunk in retrieved.chunks[:2]:
                    excerpt = _clean_excerpt(chunk.content)
                    if not excerpt:
                        continue
                    excerpts.append(
                        {
                            "text": excerpt,
                            "source": str(chunk.source_path or chunk.source_type or "Conhecimento do projeto"),
                        }
                    )
            except Exception:
                pass

        if query and not metadata_match and not excerpts:
            continue

        results.append(
            {
                "project_key": config.external_project_key,
                "name": project.name,
                "slug": project.slug,
                "description": description,
                "publication_status": _publication_status(config),
                "updated_at": config.updated_at,
                "match": "rag" if excerpts else "metadata",
                "excerpts": excerpts,
            }
        )
        if len(results) >= limit:
            break

    return {"query": query, "rag_available": rag_available, "results": results}


@router.get("/catalog/{project_key}")
def catalog_project(project_key: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    if not ws:
        raise HTTPException(404, "DevAI Invest project not found")
    row = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.external_project_key == project_key,
            InvestiaProjectConfig.public_enabled.is_(True),
        )
    ).first()
    if not row:
        raise HTTPException(404, "DevAI Invest project not found")
    config, project = row
    return _public_view(db, config, project)


@router.post("/admin/projects/{project_id}/publish")
def publish_project(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws, project, config = _config_for_admin(db, project_id)
    if config.status in {InvestiaProjectStatus.cancelled, InvestiaProjectStatus.completed}:
        raise HTTPException(409, "Projeto encerrado não pode iniciar nova captação")

    previous_status = config.status.value
    if config.status in {InvestiaProjectStatus.draft, InvestiaProjectStatus.paused}:
        config.status = InvestiaProjectStatus.fundraising
    config.public_enabled = True

    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="devai_invest.project.published",
        details={
            "project_key": config.external_project_key,
            "previous_status": previous_status,
            "status": config.status.value,
        },
    )
    db.commit()
    return _publication_view(config, project)


@router.post("/admin/projects/{project_id}/pause")
def pause_project(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws, project, config = _config_for_admin(db, project_id)
    if not config.public_enabled:
        raise HTTPException(409, "Projeto ainda não está publicado no DevAI Invest")
    if config.status in {InvestiaProjectStatus.cancelled, InvestiaProjectStatus.completed}:
        raise HTTPException(409, "Projeto encerrado não pode ser pausado")

    previous_status = config.status.value
    config.status = InvestiaProjectStatus.paused

    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="devai_invest.project.paused",
        details={
            "project_key": config.external_project_key,
            "previous_status": previous_status,
        },
    )
    db.commit()
    return _publication_view(config, project)


@router.post("/admin/projects/{project_id}/unpublish")
def unpublish_project(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws, project, config = _config_for_admin(db, project_id)
    config.public_enabled = False

    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="devai_invest.project.unpublished",
        details={
            "project_key": config.external_project_key,
            "status": config.status.value,
        },
    )
    db.commit()
    return _publication_view(config, project)
