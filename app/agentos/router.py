from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.catalog import AGENT_CATALOG
from app.agentos.contracts import ChatRequest, GoalCreate, KnowledgeIngest, RAGQuery
from app.agentos.llm import LLMClient, ModelUnavailable
from app.agentos.models import AgentGoal
from app.agentos.orchestrator import plan_goal
from app.agentos.rag import ingest, search
from app.db import get_db
from app.models import Project, Workspace
from app.security import require_access
from app.services.audit import record


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
    plan = plan_goal(payload.objective)
    item = AgentGoal(
        workspace_id=ws.id,
        project_id=payload.project_id,
        title=payload.title,
        objective=payload.objective,
        status="planned",
        plan_json=plan.model_dump_json(),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        actor="owner",
        action="agentos.goal_planned",
        details={"goal_id": item.id, "steps": len(plan.steps), "mode": plan.mode},
    )
    db.commit()
    return {"id": item.id, "status": item.status, "plan": plan.model_dump()}


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    item = db.scalar(
        select(AgentGoal).where(AgentGoal.id == goal_id, AgentGoal.workspace_id == ws.id)
    )
    if not item:
        raise HTTPException(404, "Goal not found")
    return {
        "id": item.id,
        "project_id": item.project_id,
        "title": item.title,
        "objective": item.objective,
        "status": item.status,
        "plan": json.loads(item.plan_json),
        "created_at": item.created_at,
    }


@router.post("/knowledge", status_code=201)
def ingest_knowledge(payload: KnowledgeIngest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    chunks = ingest(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        namespace=payload.namespace,
        source=payload.source,
        content=payload.content,
        metadata=payload.metadata,
    )
    record(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        actor="owner",
        action="agentos.knowledge_ingested",
        details={"namespace": payload.namespace, "source": payload.source, "chunks": len(chunks)},
    )
    db.commit()
    return {
        "chunks": len(chunks),
        "ids": [item.id for item in chunks],
        "embedding_models": sorted({item.embedding_model for item in chunks}),
        "embedding_providers": sorted({item.embedding_provider for item in chunks}),
    }


@router.post("/rag/query")
def rag_query(payload: RAGQuery, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    return {
        "query": payload.query,
        "matches": search(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            namespace=payload.namespace,
            query=payload.query,
            top_k=payload.top_k,
        ),
    }


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    matches = search(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        namespace=payload.namespace,
        query=payload.query,
        top_k=payload.top_k,
    )
    context = "\n\n".join(
        f"[{index + 1}] {item['source']}: {item['content']}"
        for index, item in enumerate(matches)
    )
    messages = [
        {
            "role": "system",
            "content": payload.system
            + "\nIf context is provided, ground factual claims in it and say when it is insufficient.",
        },
        {
            "role": "user",
            "content": f"Context:\n{context or '(no relevant context)'}\n\nQuestion:\n{payload.query}",
        },
    ]
    try:
        result = LLMClient().chat(messages)
    except ModelUnavailable as error:
        raise HTTPException(503, str(error)) from error
    return {**result, "matches": matches}
