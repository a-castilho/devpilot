from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_budget_dependency import require_ai_budget_access
from app.db import get_db
from app.mentor_models import LearningEvent, LearningSkill, SecurityFinding, SecurityScan
from app.models import Project, Task, TaskStatus
from app.security import Principal, Role, session_principal
from app.services.audit import record
from app.services.project_context import get_or_create_snapshot
from app.services.security_scanner import scan_project

router = APIRouter(prefix="/api", tags=["mentor-security"])

MentorMode = Literal["execute", "explain", "teach", "pair", "quiz"]
SkillLevel = Literal["beginner", "intermediate", "advanced", "expert"]


class MentorRequest(BaseModel):
    mode: MentorMode = "explain"
    question: str = Field(min_length=2, max_length=6_000)
    target: str | None = Field(default=None, max_length=500)
    skill: str | None = Field(default=None, max_length=120)
    level: SkillLevel | None = None
    priority: int = Field(default=60, ge=1, le=100)


class SkillUpdate(BaseModel):
    level: SkillLevel
    confidence: int = Field(default=70, ge=0, le=100)
    concepts_seen: list[str] = Field(default_factory=list, max_length=80)
    needs_review: list[str] = Field(default_factory=list, max_length=80)


class SecurityFixRequest(BaseModel):
    apply: bool = False
    extra_instruction: str = Field(default="", max_length=2_000)


def _project(db: Session, principal: Principal, project_id: str) -> Project:
    item = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == principal.workspace_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")
    return item


def _require_ai_user(principal: Principal) -> None:
    if principal.role is Role.VIEWER:
        raise HTTPException(status_code=403, detail="Perfil de leitura não pode consumir IA")


def _skill_record(
    db: Session,
    principal: Principal,
    project: Project,
    skill: str | None,
) -> LearningSkill | None:
    if not skill:
        return None
    return db.scalar(
        select(LearningSkill).where(
            LearningSkill.workspace_id == principal.workspace_id,
            LearningSkill.user_id == principal.user_id,
            LearningSkill.project_id == project.id,
            LearningSkill.skill == skill.strip(),
        )
    )


def _mentor_prompt(mode: MentorMode, question: str, level: str, summary: dict, skill: str | None) -> str:
    prompt_summary = dict(summary)
    # Source excerpts are useful for hashing/redaction validation, but the Codex worker can
    # inspect the pinned worktree directly. Do not duplicate source code inside Task.prompt.
    prompt_summary.pop("target_excerpt", None)
    context = json.dumps(prompt_summary, ensure_ascii=False, indent=2)
    commit_sha = str(summary.get("commit_sha") or "")
    mode_instruction = {
        "explain": "Explique diretamente o que está acontecendo, por que importa e como verificar. Seja conciso.",
        "teach": "Ensine o conceito em etapas, conectando teoria ao código real. Inclua um exemplo e uma checagem de entendimento.",
        "pair": "Conduza como pair programming. Não edite arquivos. Dê uma etapa prática por vez, explique a decisão e indique como validar antes da próxima.",
        "quiz": "Crie um pequeno teste de conhecimento baseado no projeto: 3 perguntas progressivas, sem entregar as respostas antes das perguntas.",
    }[mode]
    return (
        "[DEVPILOT_MODE=analysis-read-only]\n"
        f"[DEVPILOT_REF={commit_sha}]\n"
        "Você é o DevPilot Mentor. Não modifique arquivos, não faça push, merge ou deploy. "
        "Use o repositório isolado e o contexto estrutural fornecido; confirme limites quando não houver evidência suficiente. "
        f"Adapte a linguagem ao nível {level}. {mode_instruction}\n\n"
        f"Competência principal: {skill or 'não informada'}\n"
        f"Pedido do usuário: {question.strip()}\n\n"
        "Contexto seguro e limitado do projeto (sem trecho de código persistido no prompt):\n"
        f"{context}\n\n"
        "Estruture a resposta com: Resposta curta; Evidência no projeto; Entenda o conceito; "
        "Como validar; Próximo exercício/ação. Não invente arquivos ou resultados."
    )


def _task_for_execution(
    db: Session,
    *,
    project: Project,
    payload: MentorRequest,
) -> Task:
    task = Task(
        workspace_id=project.workspace_id,
        project_id=project.id,
        title=f"DevPilot Mentor · Executar · {payload.question[:120]}",
        prompt=(
            "Pedido originado no DevPilot Mentor. Explique as decisões técnicas durante a implementação, "
            "preserve o System Design gate e a política de aprovação.\n\n"
            f"{payload.question.strip()}"
        ),
        source="mentor",
        priority=payload.priority,
        requires_approval=True,
        status=TaskStatus.awaiting_approval,
    )
    db.add(task)
    db.flush()
    return task


def _task_for_learning(
    db: Session,
    *,
    project: Project,
    payload: MentorRequest,
    level: str,
    summary: dict,
) -> Task:
    task = Task(
        workspace_id=project.workspace_id,
        project_id=project.id,
        title=f"DevPilot Mentor · {payload.mode.capitalize()} · {payload.question[:120]}",
        prompt=_mentor_prompt(payload.mode, payload.question, level, summary, payload.skill),
        source="mentor",
        priority=payload.priority,
        requires_approval=False,
        status=TaskStatus.queued,
    )
    db.add(task)
    db.flush()
    return task


@router.post("/projects/{project_id}/mentor", status_code=201)
def mentor(
    project_id: str,
    payload: MentorRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    _: None = Depends(require_ai_budget_access),
):
    _require_ai_user(principal)
    project = _project(db, principal, project_id)
    skill = payload.skill.strip() if payload.skill else None
    current = _skill_record(db, principal, project, skill)
    level = payload.level or (current.level if current else "intermediate")

    if payload.mode == "execute":
        if principal.role is Role.ANALYST:
            raise HTTPException(status_code=403, detail="Analista pode aprender e analisar, mas não iniciar execução")
        task = _task_for_execution(db, project=project, payload=payload)
        snapshot = None
    else:
        try:
            snapshot, summary = get_or_create_snapshot(db, project=project, target=payload.target)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        task = _task_for_learning(db, project=project, payload=payload, level=level, summary=summary)

    event = LearningEvent(
        workspace_id=project.workspace_id,
        user_id=principal.user_id,
        project_id=project.id,
        skill=skill,
        mode=payload.mode,
        subject=payload.question[:240],
        outcome="requested",
        details=json.dumps(
            {
                "task_id": task.id,
                "level": level,
                "target": payload.target,
                "snapshot_id": snapshot.id if snapshot else None,
            },
            ensure_ascii=False,
        ),
    )
    db.add(event)
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        task_id=task.id,
        actor=principal.actor,
        action="mentor.requested",
        details={"mode": payload.mode, "skill": skill, "level": level, "target": payload.target},
    )
    db.commit()
    return {
        "mode": payload.mode,
        "level": level,
        "task": task,
        "snapshot_id": snapshot.id if snapshot else None,
        "message": (
            "Execução criada e aguardando aprovação explícita."
            if payload.mode == "execute"
            else "Sessão de aprendizado enfileirada em modo somente leitura."
        ),
    }


@router.get("/projects/{project_id}/mentor/skills")
def list_skills(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    project = _project(db, principal, project_id)
    return db.scalars(
        select(LearningSkill)
        .where(
            LearningSkill.workspace_id == project.workspace_id,
            LearningSkill.user_id == principal.user_id,
            LearningSkill.project_id == project.id,
        )
        .order_by(LearningSkill.skill.asc())
    ).all()


@router.put("/projects/{project_id}/mentor/skills/{skill}")
def update_skill(
    project_id: str,
    skill: str,
    payload: SkillUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    if principal.role is Role.VIEWER:
        raise HTTPException(status_code=403, detail="Perfil de leitura não pode alterar perfil educacional")
    project = _project(db, principal, project_id)
    normalized = skill.strip()[:120]
    if not normalized:
        raise HTTPException(status_code=422, detail="Skill is required")
    item = _skill_record(db, principal, project, normalized)
    if not item:
        item = LearningSkill(
            workspace_id=project.workspace_id,
            user_id=principal.user_id,
            project_id=project.id,
            skill=normalized,
        )
        db.add(item)
    item.level = payload.level
    item.confidence = payload.confidence
    item.concepts_seen = json.dumps(payload.concepts_seen, ensure_ascii=False)
    item.needs_review = json.dumps(payload.needs_review, ensure_ascii=False)
    item.last_seen_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="mentor.skill_updated",
        details={"skill": normalized, "level": payload.level, "confidence": payload.confidence},
    )
    db.commit()
    return item


@router.post("/projects/{project_id}/security/scan", status_code=201)
def security_scan(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    if principal.role is Role.VIEWER:
        raise HTTPException(status_code=403, detail="Perfil de leitura não pode iniciar varreduras")
    project = _project(db, principal, project_id)
    try:
        result = scan_project(project)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    previous_open = db.scalars(
        select(SecurityFinding).where(
            SecurityFinding.workspace_id == project.workspace_id,
            SecurityFinding.project_id == project.id,
            SecurityFinding.status == "open",
        )
    ).all()
    for previous in previous_open:
        previous.status = "superseded"

    counts = result["counts"]
    summary = (
        f"{counts['critical']} crítico(s), {counts['high']} alto(s), "
        f"{counts['medium']} médio(s) e {counts['low']} baixo(s). "
        "A varredura local cobre padrões de código/configuração; CVEs de dependências exigem uma fonte de advisories separada."
    )
    scan = SecurityScan(
        workspace_id=project.workspace_id,
        project_id=project.id,
        requested_by_user_id=principal.user_id,
        status="completed",
        commit_sha=result["commit_sha"],
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
        summary=summary,
    )
    db.add(scan)
    db.flush()

    persisted = []
    for data in result["findings"]:
        finding = SecurityFinding(
            workspace_id=project.workspace_id,
            project_id=project.id,
            scan_id=scan.id,
            **data,
        )
        db.add(finding)
        persisted.append(finding)
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="security.scan_completed",
        details={
            "scan_id": scan.id,
            "commit_sha": scan.commit_sha,
            "counts": counts,
            "coverage": result["coverage"],
            "superseded_findings": len(previous_open),
        },
    )
    db.commit()
    return {"scan": scan, "findings": persisted, "coverage": result["coverage"]}


@router.get("/projects/{project_id}/security/scans")
def security_scans(
    project_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    project = _project(db, principal, project_id)
    return db.scalars(
        select(SecurityScan)
        .where(SecurityScan.workspace_id == project.workspace_id, SecurityScan.project_id == project.id)
        .order_by(SecurityScan.created_at.desc())
        .limit(limit)
    ).all()


@router.get("/projects/{project_id}/security/findings")
def security_findings(
    project_id: str,
    status: str = Query(default="open", max_length=30),
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    project = _project(db, principal, project_id)
    query = select(SecurityFinding).where(
        SecurityFinding.workspace_id == project.workspace_id,
        SecurityFinding.project_id == project.id,
    )
    if status != "all":
        query = query.where(SecurityFinding.status == status)
    return db.scalars(query.order_by(SecurityFinding.created_at.desc())).all()


@router.post("/projects/{project_id}/security/findings/{finding_id}/fix", status_code=201)
def security_fix(
    project_id: str,
    finding_id: str,
    payload: SecurityFixRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    project = _project(db, principal, project_id)
    finding = db.scalar(
        select(SecurityFinding).where(
            SecurityFinding.id == finding_id,
            SecurityFinding.workspace_id == project.workspace_id,
            SecurityFinding.project_id == project.id,
        )
    )
    if not finding:
        raise HTTPException(status_code=404, detail="Security finding not found")
    if not payload.apply:
        return {
            "finding_id": finding.id,
            "apply": False,
            "remediation": finding.remediation,
            "status": finding.status,
            "message": "Nenhuma alteração foi iniciada. Envie apply=true para criar uma tarefa sujeita a aprovação.",
        }
    if finding.status != "open":
        raise HTTPException(
            status_code=409,
            detail="Este achado pertence a um scan anterior. Execute/revise o scan atual antes de criar a correção.",
        )
    if principal.role in {Role.VIEWER, Role.ANALYST}:
        raise HTTPException(status_code=403, detail="Seu perfil pode analisar, mas não iniciar correções")

    task = Task(
        workspace_id=project.workspace_id,
        project_id=project.id,
        title=f"Correção de segurança · {finding.title}"[:240],
        prompt=(
            "Corrija somente o achado de segurança abaixo. Preserve o System Design gate, faça preflight de duplicidade, "
            "execute os testes relevantes e não faça push/merge/deploy.\n\n"
            f"Regra: {finding.rule_id}\nSeveridade: {finding.severity}\nArquivo: {finding.file_path}:{finding.line_number}\n"
            f"Impacto: {finding.impact}\nRemediação recomendada: {finding.remediation}\n"
            f"Instrução adicional: {payload.extra_instruction.strip()}"
        ),
        source="security",
        status=TaskStatus.awaiting_approval,
        requires_approval=True,
        priority=90 if finding.severity in {"critical", "high"} else 70,
    )
    db.add(task)
    db.flush()
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        task_id=task.id,
        actor=principal.actor,
        action="security.fix_requested",
        details={"finding_id": finding.id, "rule_id": finding.rule_id, "severity": finding.severity},
    )
    db.commit()
    return {
        "finding_id": finding.id,
        "apply": True,
        "task": task,
        "message": "Tarefa de correção criada e aguardando aprovação explícita.",
    }
