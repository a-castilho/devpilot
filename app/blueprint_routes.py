from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import require_access, require_super_admin
from app.services.blueprints import BlueprintError, BlueprintRegistry


router = APIRouter(prefix="/api/blueprints", dependencies=[Depends(require_access)])
REGISTRY = BlueprintRegistry(Path("data/blueprints"))
PROJECT_ROOT = Path("data/generated-projects").resolve()


class BlueprintCreate(BaseModel):
    name: str
    version: str
    type: str = ""
    status: str = "experimental"
    stack: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    files: dict[str, str]
    validation: list[str] = Field(default_factory=list)


class BlueprintMatchRequest(BaseModel):
    stack: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    project_type: str = ""
    threshold: float = Field(default=60.0, ge=0, le=100)


class BlueprintMaterializeRequest(BaseModel):
    name: str
    version: str
    project_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    parameters: dict[str, str] = Field(default_factory=dict)
    overwrite: bool = False


class BlueprintOutcomeRequest(BaseModel):
    success: bool


def fail(error: BlueprintError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(error))


@router.get("")
def list_blueprints() -> dict[str, Any]:
    return {"items": REGISTRY.list()}


@router.post("")
def create_blueprint(payload: BlueprintCreate, _=Depends(require_super_admin)) -> dict[str, Any]:
    try:
        return REGISTRY.register(payload.model_dump())
    except BlueprintError as error:
        raise fail(error) from error


@router.post("/match")
def match_blueprints(payload: BlueprintMatchRequest) -> dict[str, Any]:
    matches = REGISTRY.match(stack=payload.stack, capabilities=payload.capabilities, project_type=payload.project_type)
    items = [m.__dict__ for m in matches]
    selected = next((item for item in items if item["score"] >= payload.threshold), None)
    return {"selected": selected, "items": items, "fallback_to_generation": selected is None}


@router.post("/materialize")
def materialize(payload: BlueprintMaterializeRequest, _=Depends(require_super_admin)) -> dict[str, Any]:
    destination = (PROJECT_ROOT / payload.project_slug).resolve()
    if PROJECT_ROOT != destination and PROJECT_ROOT not in destination.parents:
        raise HTTPException(status_code=400, detail="Destino inválido")
    try:
        return REGISTRY.materialize(payload.name, payload.version, destination, payload.parameters, overwrite=payload.overwrite)
    except BlueprintError as error:
        raise fail(error) from error


@router.post("/{name}/{version}/outcome")
def record_outcome(name: str, version: str, payload: BlueprintOutcomeRequest, _=Depends(require_super_admin)) -> dict[str, Any]:
    try:
        return {"metrics": REGISTRY.record_outcome(name, version, payload.success)}
    except BlueprintError as error:
        raise fail(error) from error
