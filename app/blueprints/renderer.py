from __future__ import annotations

import re
from pathlib import PurePosixPath

from .domain import BlueprintManifest, RenderedProject

_TOKEN_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
_SECRET_NAMES = ("token", "secret", "password", "passwd", "api_key", "apikey", "private_key")


class BlueprintRenderError(ValueError):
    pass


def _validate_relative_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise BlueprintRenderError(f"unsafe blueprint path: {path}")


def _render_text(value: str, parameters: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in parameters:
            raise BlueprintRenderError(f"missing blueprint parameter: {name}")
        return str(parameters[name])

    return _TOKEN_RE.sub(replace, value)


def validate_no_embedded_secrets(manifest: BlueprintManifest) -> None:
    for item in manifest.files:
        lowered = item.content.lower()
        for name in _SECRET_NAMES:
            pattern = re.compile(rf"(?i)\b{re.escape(name)}\b\s*[:=]\s*['\"]?([^\s'\"]+)")
            for match in pattern.finditer(item.content):
                value = match.group(1)
                if value.startswith("${") or "{{" in value or value in {"", "null", "none", "changeme"}:
                    continue
                raise BlueprintRenderError(f"possible secret embedded in blueprint file {item.path}")
        if "-----begin private key-----" in lowered:
            raise BlueprintRenderError(f"private key embedded in blueprint file {item.path}")


def render_project(manifest: BlueprintManifest, parameters: dict[str, str]) -> RenderedProject:
    missing = [name for name in manifest.parameters if name not in parameters]
    if missing:
        raise BlueprintRenderError("missing blueprint parameters: " + ", ".join(sorted(missing)))

    validate_no_embedded_secrets(manifest)
    rendered: dict[str, str] = {}
    for item in manifest.files:
        path = _render_text(item.path, parameters)
        _validate_relative_path(path)
        if path in rendered:
            raise BlueprintRenderError(f"duplicate rendered path: {path}")
        rendered[path] = _render_text(item.content, parameters)

    return RenderedProject(
        blueprint_slug=manifest.slug,
        blueprint_version=manifest.version,
        files=rendered,
        parameters=dict(parameters),
    )
