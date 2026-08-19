from typing import Any

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    github_login: str = Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
    access_token: str | None = Field(default=None, min_length=8, max_length=10_000)


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
    requires_approval: bool = True


class VoiceCommand(BaseModel):
    project_id: str | None = None
    transcript: str = Field(min_length=2, max_length=20_000)


class ProviderCreate(BaseModel):
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,49}$")
    label: str = Field(min_length=2, max_length=100)
    api_key: str = Field(min_length=8, max_length=10_000)
    models: list[str] = Field(default_factory=list)
