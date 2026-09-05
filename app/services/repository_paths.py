from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings


_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def _segment(value: object, fallback: str) -> str:
    normalized = _SAFE_SEGMENT.sub("-", str(value or "").strip()).strip("-.")
    return normalized or fallback


def repository_path(project) -> Path:
    """Return a tenant/project-isolated checkout path for a persisted project."""
    workspace_key = _segment(getattr(project, "workspace_id", ""), "workspace")
    project_identity = getattr(project, "id", "") or getattr(project, "slug", "")
    project_key = _segment(project_identity, "project")
    return get_settings().repositories_dir / workspace_key / project_key
