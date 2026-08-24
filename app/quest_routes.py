from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Task
from app.quest_models import QuestMission, QuestMissionStatus, QuestProfile
from app.security import Principal, Role, session_principal
from app.services.audit import record as audit_record
from app.services.quest_engine import (
    RISK_LABELS,
    apply_reward,
    classify_task_risk,
    reward_for,
    role_can_accept,
    validate_real_task,
)


router = APIRouter(prefix="/api/quests", tags=["quests"])


class MissionCreateRequest(BaseModel):
    difficulty: int = Field(default=2, ge=1, le=5)


class MissionCompleteRequest(BaseModel):
    evidence: dict = Field(default_factory=dict)


def _now():
    return datetime.now(timezone.utc)


def _principal(principal: Principal = Depends(session_principal)) -> Principal:
    if not principal.user_id or not principal.workspace_id:
        raise HTTPException(status_code=401, detail="Sessão inválida")
    return principal


def _profile(db: Session, principal: Principal) -> QuestProfile:
    profile = db.scalar(
        select(QuestProfile).where(
            QuestProfile.workspace_id == principal.workspace_id,
            QuestProfile.user_id == principal.user_id,
        )
    )
    if profile is None:
        profile = QuestProfile(workspace_id=principal.workspace_id, user_id=principal.user_id)
        db.add(profile)
        db.flush()
    return profile


def _mission(db: Session, mission_id: str, principal: Principal) -> QuestMission:
    mission = db.scalar(
        select(QuestMission).where(
            QuestMission.id == mission_id,
            QuestMission.workspace_id == principal.workspace_id,
        )
    )
    if mission is None:
        raise HTTPException(status_code=404, detail="Missão não encontrada")
    return mission


def _serialize_mission(item: QuestMission):
    return {
        "id": item.id,
        "project_id": item.project_id,
        "task_id": item.task_id,
        "user_id": item.user_id,
        "title": item.title,
        "description": item.description,
        "risk_level": item.risk_level,
        "risk_label": RISK_LABELS[item.risk_level],
        "difficulty": item.difficulty,
        "status": item.status,
        "reward": {
            "xp": item.reward_xp,
            "stars": item.reward_stars,
            "moons": item.reward_moons,
            "swords": item.reward_swords,
        },
        "validation_summary": item.validation_summary,
        "accepted_at": item.accepted_at,
        "completed_at": item.completed_at,
    }


@router.get("/me")
def quest_profile(
    db: Session = Depends(get_db),
    principal: Principal = Depends(_principal),
):
    profile = _profile(db, principal)
    db.commit()
    return {
        "user_id": profile.user_id,
        "xp": profile.xp,
        "level": profile.level,
        "rank": profile.rank_name,
        "rewards": {"stars": profile.stars, "moons": profile.moons, "swords": profile.swords},
        "security": {
            "platform_role": principal.role.value,
            "progression_grants_permissions": False,
            "message": "Nível técnico nunca concede privilégios de sistema automaticamente.",
        },
    }


@router.get("/missions")
def list_missions(
    db: Session = Depends(get_db),
    principal: Principal = Depends(_principal),
):
    items = db.scalars(
        select(QuestMission)
        .where(QuestMission.workspace_id == principal.workspace_id)
        .order_by(QuestMission.created_at.desc())
    ).all()
    if principal.role not in {Role.SUPER_ADMIN, Role.OWNER, Role.ADMIN}:
        items = [item for item in items if item.user_id in {None, principal.user_id}]
    return [_serialize_mission(item) for item in items]


@router.post("/missions/from-task/{task_id}", status_code=201)
def create_mission_from_task(
    task_id: str,
    payload: MissionCreateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_principal),
):
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == principal.workspace_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarefa real não encontrada")
    project = db.scalar(
        select(Project).where(Project.id == task.project_id, Project.workspace_id == principal.workspace_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    existing = db.scalar(
        select(QuestMission).where(
            QuestMission.workspace_id == principal.workspace_id,
            QuestMission.task_id == task.id,
        )
    )
    if existing:
        return _serialize_mission(existing)

    risk = classify_task_risk(task)
    reward = reward_for(risk, payload.difficulty)
    mission = QuestMission(
        workspace_id=principal.workspace_id,
        project_id=project.id,
        task_id=task.id,
        title=task.title,
        description=f"Resolver tarefa real do projeto {project.name}. A recompensa só é liberada após validação do estado real da tarefa.",
        risk_level=risk,
        difficulty=payload.difficulty,
        reward_xp=reward.xp,
        reward_stars=reward.stars,
        reward_moons=reward.moons,
        reward_swords=reward.swords,
    )
    db.add(mission)
    db.flush()
    audit_record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="QUEST_MISSION_CREATED",
        project_id=project.id,
        task_id=task.id,
        details={"mission_id": mission.id, "risk": risk, "difficulty": payload.difficulty},
    )
    db.commit()
    return _serialize_mission(mission)


@router.post("/missions/{mission_id}/accept")
def accept_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_principal),
):
    mission = _mission(db, mission_id, principal)
    if mission.status == QuestMissionStatus.completed.value:
        raise HTTPException(status_code=409, detail="Missão já concluída")
    if mission.user_id and mission.user_id != principal.user_id:
        raise HTTPException(status_code=409, detail="Missão já atribuída a outro usuário")
    if not role_can_accept(principal.role, mission.risk_level):
        raise HTTPException(status_code=403, detail="Seu papel RBAC não permite aceitar este nível de risco")

    mission.user_id = principal.user_id
    mission.status = QuestMissionStatus.accepted.value
    mission.accepted_at = mission.accepted_at or _now()
    audit_record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="QUEST_MISSION_ACCEPTED",
        project_id=mission.project_id,
        task_id=mission.task_id,
        details={"mission_id": mission.id, "risk": mission.risk_level, "role": principal.role.value},
    )
    db.commit()
    return _serialize_mission(mission)


@router.post("/missions/{mission_id}/complete")
def complete_mission(
    mission_id: str,
    payload: MissionCompleteRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(_principal),
):
    mission = _mission(db, mission_id, principal)
    if mission.user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Somente o usuário que aceitou a missão pode concluí-la")
    if mission.status == QuestMissionStatus.completed.value:
        raise HTTPException(status_code=409, detail="Recompensa já concedida")
    if not role_can_accept(principal.role, mission.risk_level):
        raise HTTPException(status_code=403, detail="Seu papel RBAC não permite concluir este nível de risco")

    task = db.scalar(
        select(Task).where(Task.id == mission.task_id, Task.workspace_id == principal.workspace_id)
    )
    if task is None:
        raise HTTPException(status_code=409, detail="Tarefa real vinculada não existe mais")
    valid, summary = validate_real_task(task, mission.risk_level)
    if not valid:
        mission.status = QuestMissionStatus.blocked.value
        mission.validation_summary = summary
        audit_record(
            db,
            workspace_id=principal.workspace_id,
            actor=principal.actor,
            action="QUEST_MISSION_VALIDATION_BLOCKED",
            outcome="blocked",
            project_id=mission.project_id,
            task_id=mission.task_id,
            details={"mission_id": mission.id, "reason": summary},
        )
        db.commit()
        raise HTTPException(status_code=409, detail=summary)

    profile = _profile(db, principal)
    reward = reward_for(mission.risk_level, mission.difficulty)
    apply_reward(profile, reward)
    mission.status = QuestMissionStatus.completed.value
    mission.completed_at = _now()
    mission.validation_summary = summary
    mission.evidence_json = json.dumps(payload.evidence, sort_keys=True, default=str)
    audit_record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="QUEST_REWARD_GRANTED",
        project_id=mission.project_id,
        task_id=mission.task_id,
        details={
            "mission_id": mission.id,
            "reward": {"xp": reward.xp, "stars": reward.stars, "moons": reward.moons, "swords": reward.swords},
            "new_level": profile.level,
            "rank": profile.rank_name,
            "rbac_unchanged": True,
        },
    )
    db.commit()
    return {"mission": _serialize_mission(mission), "profile": {"xp": profile.xp, "level": profile.level, "rank": profile.rank_name, "stars": profile.stars, "moons": profile.moons, "swords": profile.swords}}
