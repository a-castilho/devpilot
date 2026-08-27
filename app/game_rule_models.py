from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import now, uid


class GameRule(Base):
    __tablename__ = "game_rules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "rule_key", "version", name="uq_game_rule_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    rule_key: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    actions_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
