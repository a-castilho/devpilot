from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .domain import BlueprintManifest, BlueprintMatch, ProjectRequirements, RenderedProject
from .matcher import match_blueprints
from .registry import BlueprintRegistry
from .renderer import render_project


class BlueprintService:
    def __init__(self, registry: BlueprintRegistry):
        self.registry = registry

    def register(self, manifest: BlueprintManifest, *, overwrite: bool = False) -> BlueprintManifest:
        return self.registry.register(manifest, overwrite=overwrite)

    def recommend(
        self,
        requirements: ProjectRequirements,
        *,
        minimum_score: float = 0.35,
        limit: int = 5,
    ) -> list[BlueprintMatch]:
        matches = match_blueprints(
            requirements,
            self.registry.list(latest_only=True),
            minimum_score=minimum_score,
        )
        return matches[: max(1, limit)]

    def render(self, slug: str, parameters: dict[str, str], *, version: str | None = None) -> RenderedProject:
        return render_project(self.registry.get(slug, version), parameters)

    def materialize(
        self,
        slug: str,
        parameters: dict[str, str],
        target: str | Path,
        *,
        version: str | None = None,
        overwrite: bool = False,
    ) -> RenderedProject:
        rendered = self.render(slug, parameters, version=version)
        root = Path(target).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for relative, content in rendered.files.items():
            destination = (root / relative).resolve()
            if root not in destination.parents and destination != root:
                raise ValueError(f"rendered file escaped target directory: {relative}")
            if destination.exists() and not overwrite:
                raise FileExistsError(str(destination))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        return rendered

    def selection_payload(self, match: BlueprintMatch) -> dict:
        return asdict(match)
