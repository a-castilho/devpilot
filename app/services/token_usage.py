from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, TokenUsage
from app.services.audit import record


@dataclass(frozen=True)
class TokenCounts:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def _int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def token_counts_from_usage(usage: dict | None) -> TokenCounts:
    """Normalize provider token metadata without estimating missing usage."""
    if not isinstance(usage, dict):
        return TokenCounts()

    input_details = usage.get("input_tokens_details") or {}
    if not isinstance(input_details, dict):
        input_details = {}

    input_tokens = _int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("promptTokenCount")
    )
    cached_input_tokens = _int(
        usage.get("cached_input_tokens")
        or input_details.get("cached_tokens")
        or usage.get("cached_tokens")
        or usage.get("cachedContentTokenCount")
    )
    output_tokens = _int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("candidatesTokenCount")
    )
    reported_total = _int(
        usage.get("total_tokens")
        or usage.get("totalTokenCount")
    )
    total_tokens = reported_total or (input_tokens + output_tokens)
    return TokenCounts(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def extract_codex_usage(stdout: str) -> TokenCounts:
    """Read the last provider-reported usage object from Codex JSONL output."""
    last_usage: dict | None = None
    fallback_usage: dict | None = None

    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue

        usage = payload.get("usage")
        if isinstance(usage, dict):
            fallback_usage = usage
            event_type = str(payload.get("type") or "").lower()
            if event_type in {"turn.completed", "turn_completed", "response.completed"}:
                last_usage = usage

        response = payload.get("response")
        if isinstance(response, dict) and isinstance(response.get("usage"), dict):
            fallback_usage = response["usage"]
            if str(payload.get("type") or "").lower().endswith("completed"):
                last_usage = response["usage"]

    return token_counts_from_usage(last_usage or fallback_usage)


def user_id_from_actor(actor: str | None) -> str | None:
    value = str(actor or "")
    if not value.startswith("user:"):
        return None
    user_id = value.removeprefix("user:").strip()
    return user_id or None


def task_user_id(db: Session, task_id: str) -> str | None:
    """Resolve the user that originated a task from its immutable audit trail."""
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.task_id == task_id)
        .order_by(AuditEvent.created_at.asc())
    ).all()
    for event in events:
        user_id = user_id_from_actor(event.actor)
        if user_id:
            return user_id
    return None


def serialize_usage(item: TokenUsage) -> dict:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "project_id": item.project_id,
        "task_id": item.task_id,
        "run_id": item.run_id,
        "provider": item.provider,
        "model": item.model,
        "operation": item.operation,
        "input_tokens": item.input_tokens,
        "cached_input_tokens": item.cached_input_tokens,
        "output_tokens": item.output_tokens,
        "total_tokens": item.total_tokens,
        "source": item.source,
        "attempt": item.attempt,
        "created_at": item.created_at,
    }


def record_usage(
    db: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    provider: str,
    model: str,
    operation: str,
    counts: TokenCounts,
    project_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    attempt: int = 1,
    source: str = "provider-reported",
) -> TokenUsage | None:
    """Persist only actual provider-reported tokens; never fabricate an estimate."""
    if counts.total_tokens <= 0:
        return None

    item = TokenUsage(
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        provider=str(provider or "unknown")[:50],
        model=str(model or "default")[:120],
        operation=str(operation or "unknown")[:80],
        input_tokens=counts.input_tokens,
        cached_input_tokens=counts.cached_input_tokens,
        output_tokens=counts.output_tokens,
        total_tokens=counts.total_tokens,
        source=source,
        attempt=max(1, int(attempt or 1)),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        actor=f"user:{user_id}" if user_id else "system",
        action="tokens.consumed",
        details={
            "usage_id": item.id,
            "provider": item.provider,
            "model": item.model,
            "operation": item.operation,
            "input_tokens": item.input_tokens,
            "cached_input_tokens": item.cached_input_tokens,
            "output_tokens": item.output_tokens,
            "total_tokens": item.total_tokens,
            "source": source,
            "attempt": item.attempt,
        },
    )
    return item
