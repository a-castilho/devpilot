from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Small immutable event shared by AgentOS use cases.

    The domain event intentionally has no FastAPI, SQLAlchemy or provider dependency. Driving
    and driven adapters decide how to persist, publish or observe it.
    """

    name: str
    workspace_id: str
    project_id: str | None = None
    task_id: str | None = None
    actor: str = "owner"
    outcome: str = "success"
    payload: Mapping[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
