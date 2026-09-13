from __future__ import annotations

import json
import re
from pathlib import Path

from app.blueprint_routes import registry, service
from app.models import Project

_SAFE_DB = re.compile(r"[^a-zA-Z0-9_]+")
_MARKER = Path(".devpilot/blueprint.json")


def _config(project: Project) -> dict:
    try:
        value = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parameters(project: Project, config: dict, required: tuple[str, ...]) -> dict[str, str]:
    supplied = config.get("blueprint_parameters") if isinstance(config.get("blueprint_parameters"), dict) else {}
    params = {str(k): str(v) for k, v in supplied.items() if v is not None}
    defaults = {
        "project_name": str(project.name or project.slug or "DevPilot Project"),
        "database_name": _SAFE_DB.sub("_", str(project.slug or "app")).strip("_") or "app",
    }
    for name in required:
        if name not in params and name in defaults:
            params[name] = defaults[name]
    return params


def prepare_blueprint_workspace(project: Project, repository: Path) -> dict | None:
    """Materialize the selected blueprint once, creating only missing files.

    Existing project files always win. This makes blueprint reuse safe for repositories
    that already contain code and ensures the AI receives a concrete validated base and
    only needs to generate the project-specific delta.
    """
    config = _config(project)
    if config.get("generation_strategy") != "blueprint_delta":
        return None
    selected = config.get("blueprint")
    if not isinstance(selected, dict) or not selected.get("slug"):
        return None

    marker = repository / _MARKER
    slug = str(selected["slug"])
    version = str(selected.get("version") or "") or None
    if marker.is_file():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
            if current.get("slug") == slug and (not version or current.get("version") == version):
                return current
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    manifest = registry.get(slug, version)
    params = _parameters(project, config, manifest.parameters)
    rendered = service.render(slug, params, version=manifest.version)

    created: list[str] = []
    skipped: list[str] = []
    root = repository.resolve()
    for relative, content in rendered.files.items():
        destination = (root / relative).resolve()
        if root not in destination.parents and destination != root:
            raise ValueError(f"blueprint path escaped repository: {relative}")
        if destination.exists():
            skipped.append(relative)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        created.append(relative)

    result = {
        "slug": rendered.blueprint_slug,
        "version": rendered.blueprint_version,
        "created": created,
        "skipped_existing": skipped,
        "generation_strategy": "blueprint_delta",
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
