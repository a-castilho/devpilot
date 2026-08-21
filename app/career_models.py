from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class CareerProfile(Base):
    __tablename__ = "career_profiles"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    source_sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    linkedin_baseline_json: Mapped[str] = mapped_column(Text, default="{}")
    approved_profile_json: Mapped[str] = mapped_column(Text, default="{}")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
