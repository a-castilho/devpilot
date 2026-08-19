from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    name: str
    role: str
    description: str
    capabilities: list[str]
    default_tools: list[str] = Field(default_factory=list)
    max_parallelism: int = 1


class AgentStep(BaseModel):
    id: str
    agent: str
    title: str
    objective: str
    depends_on: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    approval_required: bool = False


class AgentPlan(BaseModel):
    objective: str
    mode: Literal["resource-light", "standard"] = "resource-light"
    steps: list[AgentStep]


class GoalCreate(BaseModel):
    project_id: str | None = None
    title: str = Field(min_length=2, max_length=240)
    objective: str = Field(min_length=5, max_length=100_000)


class KnowledgeIngest(BaseModel):
    project_id: str | None = None
    namespace: str = Field(default="default", pattern=r"^[A-Za-z0-9._/-]{1,100}$")
    source: str = Field(default="manual", max_length=500)
    content: str = Field(min_length=1, max_length=500_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGQuery(BaseModel):
    project_id: str | None = None
    namespace: str = Field(default="default", pattern=r"^[A-Za-z0-9._/-]{1,100}$")
    query: str = Field(min_length=2, max_length=20_000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatRequest(RAGQuery):
    system: str = Field(
        default="You are a precise software engineering agent. Use retrieved context when relevant.",
        max_length=20_000,
    )
