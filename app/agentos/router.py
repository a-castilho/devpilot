from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.errors import CommandExecutionError, ExecutionNotFound, ModelUnavailable
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.container import build_agentos_services
from app.agentos.contracts import (
    ChatRequest,
    CouncilRequest,
    ExecutionResume,
    ExecutionStart,
    GoalCreate,
    KnowledgeIngest,
    MemoryIngest,
    MemoryRecall,
    RAGQuery,
)
from app.db import get_db
from app.models import Project, Task, Workspace
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


def _task_or_404(db: Session, workspace_id: str, task_id: str) -> Task:
    item = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Task not found")
    return item


def _execution_payload(execution, steps) -> dict:
    return {
        "id": execution.id,
        "goal_id": execution.goal_id,
        "project_id": execution.project_id,
        "status": execution.status,
        "idempotency_key": execution.idempotency_key,
        "current_step_id": execution.current_step_id,
        "failure_reason": execution.failure_reason,
        "checkpoint": execution.checkpoint,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "steps": [
            {
                "id": step.step_id,
                "agent": step.agent,
                "title": step.title,
                "objective": step.objective,
                "depends_on": step.depends_on,
                "tools": step.tools,
                "approval_required": step.approval_required,
                "approved_at": step.approved_at,
                "status": step.status,
                "attempt": step.attempt,
                "max_attempts": step.max_attempts,
                "external_task_id": step.external_task_id,
                "output": step.output,
                "checkpoint": step.checkpoint,
                "error": step.error,
                "next_attempt_at": step.next_attempt_at,
            }
            for step in steps
        ],
    }


@router.get("/platform")
def platform_status(db: Session = Depends(get_db)):
    _workspace(db)
    return build_agentos_services(db).kernel.describe()


@router.get("/agents")
def list_agents():
    return [definition.model_dump() for definition in AGENT_CATALOG.values()]


@router.get("/tools")
def list_tools(agent: str | None = Query(default=None), db: Session = Depends(get_db)):
    _workspace(db)
    if agent is not None and agent not in AGENT_CATALOG:
        raise HTTPException(404, "Agent not found")
    return build_agentos_services(db).tools.list_tools(agent=agent)


@router.get("/apps")
def list_apps(db: Session = Depends(get_db)):
    ws = _workspace(db)
    return build_agentos_services(db).apps.list_apps(workspace_id=ws.id)


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


@router.post("/goals/{goal_id}/executions", status_code=201)
def start_execution(goal_id: str, payload: ExecutionStart, db: Session = Depends(get_db)):
    ws = _workspace(db)
    service = build_agentos_services(db).executions
    try:
        execution = service.start(
            workspace_id=ws.id,
            goal_id=goal_id,
            idempotency_key=payload.idempotency_key,
            max_attempts=payload.max_attempts,
        )
    except ExecutionNotFound as error:
        raise HTTPException(404, str(error)) from error
    return _execution_payload(execution, service.steps(execution_id=execution.id))


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    service = build_agentos_services(db).executions
    execution = service.get(workspace_id=ws.id, execution_id=execution_id)
    if not execution:
        raise HTTPException(404, "Execution not found")
    return _execution_payload(execution, service.steps(execution_id=execution.id))


@router.post("/executions/{execution_id}/steps/{step_id}/approve")
def approve_execution_step(
    execution_id: str,
    step_id: str,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    service = build_agentos_services(db).executions
    try:
        step = service.approve_step(
            workspace_id=ws.id,
            execution_id=execution_id,
            step_id=step_id,
        )
    except ExecutionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except CommandExecutionError as error:
        raise HTTPException(409, str(error)) from error
    return {"execution_id": execution_id, "step_id": step.step_id, "status": step.status}


@router.post("/executions/{execution_id}/resume")
def resume_execution(
    execution_id: str,
    payload: ExecutionResume,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    service = build_agentos_services(db).executions
    try:
        execution = service.resume(
            workspace_id=ws.id,
            execution_id=execution_id,
            reset_attempts=payload.reset_attempts,
        )
    except ExecutionNotFound as error:
        raise HTTPException(404, str(error)) from error
    except CommandExecutionError as error:
        raise HTTPException(409, str(error)) from error
    return _execution_payload(execution, service.steps(execution_id=execution.id))


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


@router.post("/memory", status_code=201)
def ingest_memory(payload: MemoryIngest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    services = build_agentos_services(db)
    project_id = payload.project_id

    if payload.scope == "global":
        if project_id is not None:
            raise HTTPException(422, "Global memory must not be tied to a project")
    elif payload.scope == "project":
        if project_id is None:
            raise HTTPException(422, "project_id is required for project memory")
        _project_or_404(db, ws.id, project_id)
    elif payload.scope == "goal":
        if payload.goal_id is None:
            raise HTTPException(422, "goal_id is required for goal memory")
        goal = services.goals.get_goal(workspace_id=ws.id, goal_id=payload.goal_id)
        if not goal:
            raise HTTPException(404, "Goal not found")
        if project_id is not None and project_id != goal.project_id:
            raise HTTPException(409, "Goal does not belong to project")
        project_id = goal.project_id
    elif payload.scope == "task":
        if payload.task_id is None:
            raise HTTPException(422, "task_id is required for task memory")
        task = _task_or_404(db, ws.id, payload.task_id)
        if project_id is not None and project_id != task.project_id:
            raise HTTPException(409, "Task does not belong to project")
        project_id = task.project_id

    try:
        result = services.memory.ingest(
            workspace_id=ws.id,
            project_id=project_id,
            scope=payload.scope,
            goal_id=payload.goal_id,
            task_id=payload.task_id,
            source=payload.source,
            content=payload.content,
            metadata=payload.metadata,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        "scope": payload.scope,
        "chunks": result.chunks,
        "ids": result.ids,
        "embedding_models": result.models,
        "embedding_providers": result.providers,
    }


@router.post("/memory/recall")
def recall_memory(payload: MemoryRecall, db: Session = Depends(get_db)):
    ws = _workspace(db)
    services = build_agentos_services(db)
    project_id = payload.project_id

    if payload.goal_id:
        goal = services.goals.get_goal(workspace_id=ws.id, goal_id=payload.goal_id)
        if not goal:
            raise HTTPException(404, "Goal not found")
        if project_id is not None and project_id != goal.project_id:
            raise HTTPException(409, "Goal does not belong to project")
        project_id = project_id or goal.project_id
    if payload.task_id:
        task = _task_or_404(db, ws.id, payload.task_id)
        if project_id is not None and project_id != task.project_id:
            raise HTTPException(409, "Task does not belong to project")
        project_id = project_id or task.project_id
    if project_id:
        _project_or_404(db, ws.id, project_id)

    matches = services.memory.recall(
        workspace_id=ws.id,
        project_id=project_id,
        goal_id=payload.goal_id,
        task_id=payload.task_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return {"query": payload.query, "matches": matches}


@router.post("/council")
def council(payload: CouncilRequest, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project_or_404(db, ws.id, payload.project_id)
    try:
        return build_agentos_services(db).council.deliberate(
            workspace_id=ws.id,
            project_id=payload.project_id,
            namespace=payload.namespace,
            question=payload.question,
            members=payload.members,
            top_k=payload.top_k,
            consensus_threshold=payload.consensus_threshold,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


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
