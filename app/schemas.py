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
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    github_login: str = Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
    access_token: str | None = Field(default=None, min_length=8, max_length=10_000)

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return normalize_organization_identifier(value, max_length=100)

    @field_validator("github_login", mode="before")
    @classmethod
    def normalize_github_login(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return normalize_organization_identifier(value, max_length=39)

    @model_validator(mode="after")
    def require_managed_organization_token(self):
        if self.github_login.lower() == "a-castilho" and not self.access_token:
            raise ValueError(
                "Para a organização a-castilho, informe um Fine-grained PAT com Resource owner = a-castilho."
            )
        return self


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    access_token: str | None = Field(default=None, min_length=8, max_length=10_000)


class OrganizationSync(BaseModel):
    import_projects: bool = True


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = ""
    repository_url: str = Field(min_length=3, max_length=500)
    organization_id: str | None = None
    default_branch: str = Field(default="main", pattern=r"^[A-Za-z0-9._/-]+$")
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    description: str | None = None
    repository_url: str | None = Field(default=None, min_length=3, max_length=500)
    organization_id: str | None = None
    default_branch: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._/-]+$")
    agents_md: str | None = Field(default=None, max_length=100_000)
    codex_config: dict[str, Any] | None = None
    status: str | None = None


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=2, max_length=240)
    prompt: str = Field(min_length=5, max_length=100_000)
    source: str = Field(default="dashboard", pattern=r"^(dashboard|voice|api)$")
    priority: int = Field(default=50, ge=0, le=100)
    requires_approval: bool = False


class VoiceCommand(BaseModel):
    project_id: str | None = None
    transcript: str = Field(min_length=2, max_length=20_000)


class ProviderCreate(BaseModel):
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,49}$")
    label: str = Field(min_length=2, max_length=100)
    api_key: str = Field(min_length=8, max_length=10_000)
    models: list[str] = Field(default_factory=list)
