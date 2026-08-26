from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import now, uid
from app.db import Base


class ProductConnection(Base):
    """Governed link between a DevPilot product and another product/provider.

    Secrets never live here. External links only reference an existing
    ProviderCredential so vault/encryption remains centralized.
    """

    __tablename__ = "product_connections"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_project_id",
            "target_kind",
            "target_ref",
            "environment",
            name="uq_product_connection_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    source_project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(20), index=True)  # project | provider
    target_ref: Mapped[str] = mapped_column(String(120), index=True)
    provider_credential_id: Mapped[str | None] = mapped_column(
        ForeignKey("provider_credentials.id"), index=True
    )
    environment: Mapped[str] = mapped_column(String(30), default="production", index=True)
    scopes: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
