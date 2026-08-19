from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.errors import ModelUnavailable
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.container import build_agentos_services
from app.agentos.contracts import ChatRequest, GoalCreate, KnowledgeIngest, RAGQuery
from app.db import get_db
from app.models import Project, Workspace
from app.security import require_access


router = APIRouter(prefix="/api/agentos", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def _project_or_404(db: Session, workspace_id: str, project_id: str | None) -> Project | None:
    if project_id is None:
        return None
    item = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not item:
        raise HTTPException(404, "Project not found")
    return item


@router.get("/agents")
def list_agents():
    return [definition.model_dump() for definition in AGENT_CATALOG.values()]


@router.post("/goals", status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    services = build_agentos_services(db)
    item = services.goals.plan_goal(
        workspace_id=ws.id,
        project_id=payload.project_id,
        title=payload.title,
        objective=payload.objective,
    )
    return {"id": item.id, "status": item.status, "plan": item.plan.model_dump()}


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    item = build_agentos_services(db).goals.get_goal(workspace_id=ws.id, goal_id=goal_id)
    if not item:
        raise HTTPException(404, "Goal not found")
    return {
        "id": item.id,
        "project_id": item.project_id,
        "title": item.title,
        "objective": item.objective,
        "status": item.status,
        "plan": item.plan.model_dump(),
        "created_at": item.created_at,
    }


@router.post("/knowledge", status_code=201)
def ingest_knowledge(payload: KnowledgeIngest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    result = build_agentos_services(db).knowledge.ingest(
        workspace_id=ws.id,
        project_id=payload.project_id,
        namespace=payload.namespace,
        source=payload.source,
        content=payload.content,
        metadata=payload.metadata,
    )
    return {
        "chunks": result.chunks,
        "ids": result.ids,
        "embedding_models": result.models,
        "embedding_providers": result.providers,
    }


@router.post("/rag/query")
def rag_query(payload: RAGQuery, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    matches = build_agentos_services(db).knowledge.search(
        workspace_id=ws.id,
        project_id=payload.project_id,
        namespace=payload.namespace,
        query=payload.query,
        top_k=payload.top_k,
    )
    return {"query": payload.query, "matches": matches}


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    try:
        return build_agentos_services(db).chat.answer(
            workspace_id=ws.id,
            project_id=payload.project_id,
            namespace=payload.namespace,
            query=payload.query,
            top_k=payload.top_k,
            system=payload.system,
        )
    except ModelUnavailable as error:
        raise HTTPException(503, str(error)) from error
