from datetime import datetime
import re
from typing import Any
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_organization_identifier(value: str, *, max_length: int) -> str:
    """Convert a display name into a GitHub-safe identifier."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")[:max_length].strip("-")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=4096)


class BootstrapUserRequest(LoginRequest):
    pass


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthStatusResponse(BaseModel):
    bootstrap_required: bool
    password_login: bool = True
    local_bootstrap_available: bool = False


class CurrentUserResponse(BaseModel):
    id: str | None = None
    workspace_id: str | None = None
    email: str | None = None
    role: str
    active: bool = True
    bootstrap: bool = False
    full_name: str | None = None
    phone: str | None = None
    job_title: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=500)
    locale: str = Field(default="pt-BR", min_length=2, max_length=20)
    timezone: str = Field(default="America/Sao_Paulo", min_length=3, max_length=80)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=4096)
    role: str = Field(default="VIEWER", min_length=4, max_length=30)
    full_name: str | None = Field(default=None, max_length=160)
    confirmation_password: str | None = Field(default=None, min_length=8, max_length=4096)


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, min_length=4, max_length=30)
    active: bool | None = None
    full_name: str | None = Field(default=None, max_length=160)
    confirmation_password: str | None = Field(default=None, min_length=8, max_length=4096)


class UserResponse(BaseModel):
    id: str
    workspace_id: str
    email: str
    full_name: str | None
    role: str
    active: bool
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    provider: str = Field(default="github", max_length=40)
    namespace: str | None = Field(default=None, max_length=120)
    github_token: str | None = Field(default=None, max_length=4096)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        slug = normalize_organization_identifier(value, max_length=100)
        if len(slug) < 2:
            raise ValueError("slug inválido")
        return slug


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=40)
    namespace: str | None = Field(default=None, max_length=120)
    github_token: str | None = Field(default=None, max_length=4096)
    active: bool | None = None


class OrganizationResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    slug: str
    description: str | None
    provider: str
    namespace: str | None
    active: bool
    created_at: datetime


class ProjectCreate(BaseModel):
    organization_id: str | None = None
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    repository_url: str = Field(min_length=1, max_length=1000)
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    agents_md: str = Field(default="", max_length=100000)
    codex_config: dict[str, Any] | str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        slug = normalize_organization_identifier(value, max_length=120)
        if len(slug) < 2:
            raise ValueError("slug inválido")
        return slug


class ProjectUpdate(BaseModel):
    organization_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    repository_url: str | None = Field(default=None, min_length=1, max_length=1000)
    default_branch: str | None = Field(default=None, min_length=1, max_length=120)
    agents_md: str | None = Field(default=None, max_length=100000)
    codex_config: dict[str, Any] | str | None = None


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    organization_id: str | None
    name: str
    slug: str
    description: str | None
    repository_url: str
    default_branch: str
    agents_md: str
    codex_config: str
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=2, max_length=300)
    prompt: str = Field(min_length=1, max_length=100000)
    priority: int = Field(default=50, ge=0, le=100)
    source: str = Field(default="dashboard", max_length=40)
    skill: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    prompt: str | None = Field(default=None, min_length=1, max_length=100000)
    priority: int | None = Field(default=None, ge=0, le=100)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    project_id: str
    title: str
    prompt: str
    priority: int
    source: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProviderCredentialCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    label: str = Field(default="default", min_length=1, max_length=100)
    api_key: str = Field(min_length=6, max_length=4096)
    models: list[str] = Field(default_factory=list)
    enabled: bool = True


class ProviderCredentialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=6, max_length=4096)
    models: list[str] | None = None
    enabled: bool | None = None


class ProviderCredentialResponse(BaseModel):
    id: str
    provider: str
    label: str
    models: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    attempt: int
    status: str
    branch: str | None
    commit_sha: str | None
    pull_request_url: str | None
    summary: str | None
    started_at: datetime
    finished_at: datetime | None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    task_id: str | None
    kind: str
    content: str
    created_at: datetime


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    actor: str
    action: str
    outcome: str
    details: str
    created_at: datetime


class OrganizationProvisionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    provider: str = Field(default="github", max_length=40)
    namespace: str | None = Field(default=None, max_length=120)
    github_token: str | None = Field(default=None, max_length=4096)

    @field_validator("slug")
    @classmethod
    def normalize_optional_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = normalize_organization_identifier(value, max_length=100)
        if len(slug) < 2:
            raise ValueError("slug inválido")
        return slug


class ProjectProvisionCreate(BaseModel):
    organization_id: str | None = None
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    agents_md: str = Field(default="", max_length=100000)
    codex_config: dict[str, Any] | str | None = None
    private: bool = True

    @field_validator("slug")
    @classmethod
    def normalize_optional_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = normalize_organization_identifier(value, max_length=120)
        if len(slug) < 2:
            raise ValueError("slug inválido")
        return slug


class ProjectDeferredCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    agents_md: str = Field(default="", max_length=100000)
    codex_config: dict[str, Any] | str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_optional_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = normalize_organization_identifier(value, max_length=120)
        if len(slug) < 2:
            raise ValueError("slug inválido")
        return slug


class GoalCreate(BaseModel):
    project_id: str
    objective: str = Field(min_length=1, max_length=2000)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk_level: int = Field(default=2, ge=1, le=5)


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    project_id: str
    objective: str
    status: str
    risk_level: int
    created_at: datetime
    updated_at: datetime
