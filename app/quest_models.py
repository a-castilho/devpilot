from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import now, uid


class QuestMissionStatus(str, enum.Enum):
    available = "available"
    accepted = "accepted"
    validating = "validating"
    completed = "completed"
    blocked = "blocked"


class QuestProfile(Base):
    __tablename__ = "quest_profiles"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    moons: Mapped[int] = mapped_column(Integer, default=0)
    swords: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    rank_name: Mapped[str] = mapped_column(String(80), default="Observador")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class QuestMission(Base):
    __tablename__ = "quest_missions"
    __table_args__ = (UniqueConstraint("workspace_id", "task_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default=QuestMissionStatus.available.value, index=True)
    reward_xp: Mapped[int] = mapped_column(Integer, default=100)
    reward_stars: Mapped[int] = mapped_column(Integer, default=1)
    reward_moons: Mapped[int] = mapped_column(Integer, default=0)
    reward_swords: Mapped[int] = mapped_column(Integer, default=0)
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    validation_summary: Mapped[str] = mapped_column(Text, default="")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
