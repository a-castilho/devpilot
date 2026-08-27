from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.game_rule_engine import RuleSpec, evaluate_rules, validate_actions, validate_conditions
from app.game_rule_models import GameRule
from app.security import Principal, require_roles, Role


router = APIRouter(prefix="/api/game/rules", tags=["game-rules"])
_super_admin = require_roles(Role.SUPER_ADMIN)


class GameRuleInput(BaseModel):
    rule_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=4000)
    event_type: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    priority: int = Field(default=100, ge=0, le=10000)
    conditions: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=50)


class GameRulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    event_type: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    priority: int | None = Field(default=None, ge=0, le=10000)
    conditions: list[dict[str, Any]] | None = Field(default=None, max_length=50)
    actions: list[dict[str, Any]] | None = Field(default=None, min_length=1, max_length=50)


class SimulationInput(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    event: dict[str, Any] = Field(default_factory=dict)
    draft_rule_id: str | None = None


def _json_load(value: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _rule_dict(rule: GameRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "rule_key": rule.rule_key,
        "version": rule.version,
        "name": rule.name,
        "description": rule.description,
        "status": rule.status,
        "event_type": rule.event_type,
        "priority": rule.priority,
        "conditions": _json_load(rule.conditions_json),
        "actions": _json_load(rule.actions_json),
        "published_at": rule.published_at,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _spec(rule: GameRule) -> RuleSpec:
    return RuleSpec(
        id=rule.id,
        rule_key=rule.rule_key,
        version=rule.version,
        event_type=rule.event_type,
        priority=rule.priority,
        conditions=_json_load(rule.conditions_json),
        actions=_json_load(rule.actions_json),
    )


def _validated(conditions: list[dict[str, Any]], actions: list[dict[str, Any]]) -> tuple[str, str]:
    try:
        safe_conditions = validate_conditions(conditions)
        safe_actions = validate_actions(actions)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return json.dumps(safe_conditions, ensure_ascii=False), json.dumps(safe_actions, ensure_ascii=False)


@router.get("")
def list_rules(
    principal: Principal = Depends(_super_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(GameRule)
        .where(GameRule.workspace_id == principal.workspace_id)
        .order_by(GameRule.rule_key, GameRule.version.desc())
    ).all()
    return [_rule_dict(row) for row in rows]


@router.post("", status_code=201)
def create_rule(
    payload: GameRuleInput,
    principal: Principal = Depends(_super_admin),
    db: Session = Depends(get_db),
):
    conditions_json, actions_json = _validated(payload.conditions, payload.actions)
    max_version = db.scalar(
        select(func.max(GameRule.version)).where(
            GameRule.workspace_id == principal.workspace_id,
            GameRule.rule_key == payload.rule_key,
        )
    ) or 0
    rule = GameRule(
        workspace_id=principal.workspace_id,
        rule_key=payload.rule_key,
        version=max_version + 1,
        name=payload.name.strip(),
        description=payload.description.strip(),
        status="draft",
        event_type=payload.event_type.strip(),
        priority=payload.priority,
        conditions_json=conditions_json,
        actions_json=actions_json,
        created_by_user_id=principal.user_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: str,
    payload: GameRulePatch,
    principal: Principal = Depends(_super_admin),
    db: Session = Depends(get_db),
):
    rule = db.scalar(select(GameRule).where(GameRule.id == rule_id, GameRule.workspace_id == principal.workspace_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    if rule.status != "draft":
        raise HTTPException(status_code=409, detail="Versões publicadas são imutáveis; crie uma nova versão")

    values = payload.model_dump(exclude_unset=True)
    conditions = values.pop("conditions", None)
    actions = values.pop("actions", None)
    if conditions is not None or actions is not None:
        conditions_json, actions_json = _validated(
            conditions if conditions is not None else _json_load(rule.conditions_json),
            actions if actions is not None else _json_load(rule.actions_json),
        )
        rule.conditions_json = conditions_json
        rule.actions_json = actions_json
    for key, value in values.items():
        if value is not None:
            setattr(rule, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.post("/{rule_id}/publish")
def publish_rule(
    rule_id: str,
    principal: Principal = Depends(_super_admin),
    db: Session = Depends(get_db),
):
    rule = db.scalar(select(GameRule).where(GameRule.id == rule_id, GameRule.workspace_id == principal.workspace_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    if rule.status != "draft":
        raise HTTPException(status_code=409, detail="Somente rascunhos podem ser publicados")

    previous = db.scalars(
        select(GameRule).where(
            GameRule.workspace_id == principal.workspace_id,
            GameRule.rule_key == rule.rule_key,
            GameRule.status == "published",
        )
    ).all()
    for item in previous:
        item.status = "archived"
    rule.status = "published"
    rule.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return _rule_dict(rule)


@router.post("/simulate")
def simulate_rules(
    payload: SimulationInput,
    principal: Principal = Depends(_super_admin),
    db: Session = Depends(get_db),
):
    if payload.draft_rule_id:
        draft = db.scalar(
            select(GameRule).where(
                GameRule.id == payload.draft_rule_id,
                GameRule.workspace_id == principal.workspace_id,
                GameRule.status == "draft",
            )
        )
        if draft is None:
            raise HTTPException(status_code=404, detail="Rascunho não encontrado")
        rules = [_spec(draft)]
    else:
        rows = db.scalars(
            select(GameRule).where(
                GameRule.workspace_id == principal.workspace_id,
                GameRule.status == "published",
                GameRule.event_type == payload.event_type,
            )
        ).all()
        rules = [_spec(row) for row in rows]
    return {"dry_run": True, **evaluate_rules(rules, payload.event_type, payload.event)}
