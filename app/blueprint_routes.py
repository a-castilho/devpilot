from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.blueprints import (
    BlueprintFile,
    BlueprintManifest,
    BlueprintRegistry,
    BlueprintRenderError,
    BlueprintService,
    BlueprintStatus,
    ProjectRequirements,
)
from app.blueprints.defaults import install_builtin_blueprints
from app.security import require_access, require_super_admin


REGISTRY_ROOT = Path("data/blueprints")
registry = BlueprintRegistry(REGISTRY_ROOT)
install_builtin_blueprints(registry)
service = BlueprintService(registry)
router = APIRouter(prefix="/blueprints", dependencies=[Depends(require_access)])


class BlueprintFilePayload(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=2_000_000)
    executable: bool = False


class BlueprintCreatePayload(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    name: str = Field(min_length=2, max_length=150)
    version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+){0,2}(?:[-+][A-Za-z0-9.-]+)?$")
    description: str = Field(default="", max_length=10_000)
    kind: str = Field(default="generic", max_length=60)
    status: BlueprintStatus = BlueprintStatus.experimental
    stack: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    files: list[BlueprintFilePayload] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    overwrite: bool = False


class BlueprintRecommendPayload(BaseModel):
    description: str = Field(default="", max_length=20_000)
    stack: dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    minimum_score: float = Field(default=0.35, ge=0, le=1)
    limit: int = Field(default=5, ge=1, le=20)


class BlueprintRenderPayload(BaseModel):
    slug: str
    version: str | None = None
    parameters: dict[str, str] = Field(default_factory=dict)


class BlueprintUsagePayload(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    score: float = Field(default=0, ge=0, le=1)
    outcome: str = Field(default="selected", max_length=40)
    metadata: dict = Field(default_factory=dict)


@router.get("")
def list_blueprints(latest_only: bool = True):
    return [item.to_dict() for item in registry.list(latest_only=latest_only)]


@router.get("/metrics")
def blueprint_metrics():
    return registry.metrics()


@router.get("/{slug}")
def get_blueprint(slug: str, version: str | None = None):
    try:
        return registry.get(slug, version).to_dict()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Blueprint não encontrado.") from error


@router.post("", status_code=201)
def create_blueprint(payload: BlueprintCreatePayload, _: str = Depends(require_super_admin)):
    manifest = BlueprintManifest(
        slug=payload.slug,
        name=payload.name,
        version=payload.version,
        description=payload.description,
        kind=payload.kind,
        status=payload.status,
        stack=payload.stack,
        capabilities=tuple(payload.capabilities),
        parameters=tuple(payload.parameters),
        files=tuple(BlueprintFile(**item.model_dump()) for item in payload.files),
        tags=tuple(payload.tags),
        metadata=payload.metadata,
    )
    try:
        return service.register(manifest, overwrite=payload.overwrite).to_dict()
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except BlueprintRenderError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/recommend")
def recommend_blueprint(payload: BlueprintRecommendPayload):
    requirements = ProjectRequirements(
        description=payload.description,
        stack=payload.stack,
        capabilities=tuple(payload.capabilities),
        tags=tuple(payload.tags),
    )
    return [service.selection_payload(item) for item in service.recommend(
        requirements,
        minimum_score=payload.minimum_score,
        limit=payload.limit,
    )]


@router.post("/render")
def render_blueprint(payload: BlueprintRenderPayload):
    try:
        rendered = service.render(payload.slug, payload.parameters, version=payload.version)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Blueprint não encontrado.") from error
    except BlueprintRenderError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "blueprint_slug": rendered.blueprint_slug,
        "blueprint_version": rendered.blueprint_version,
        "files": rendered.files,
        "parameters": rendered.parameters,
    }


@router.post("/usage", status_code=204)
def record_blueprint_usage(payload: BlueprintUsagePayload):
    registry.record_usage(**payload.model_dump())
    return None
