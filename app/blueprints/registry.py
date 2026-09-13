from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .domain import BlueprintManifest
from .renderer import validate_no_embedded_secrets


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _version_key(version: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in version.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        values.append(int(digits or 0))
    return tuple(values)


class BlueprintRegistry:
    """Portable, dependency-free registry persisted as JSON files.

    Storage layout is intentionally simple so this package can be moved to another
    application or replaced by a database adapter without changing the domain API.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "usage").mkdir(exist_ok=True)

    def register(self, manifest: BlueprintManifest, *, overwrite: bool = False) -> BlueprintManifest:
        validate_no_embedded_secrets(manifest)
        folder = self.root / manifest.slug / manifest.version
        path = folder / "manifest.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"blueprint already exists: {manifest.slug}@{manifest.version}")
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def get(self, slug: str, version: str | None = None) -> BlueprintManifest:
        base = self.root / slug
        if not base.exists():
            raise KeyError(slug)
        selected = version
        if selected is None:
            versions = [item.name for item in base.iterdir() if item.is_dir() and (item / "manifest.json").exists()]
            if not versions:
                raise KeyError(slug)
            selected = max(versions, key=_version_key)
        path = base / selected / "manifest.json"
        if not path.exists():
            raise KeyError(f"{slug}@{selected}")
        return BlueprintManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(self, *, latest_only: bool = True) -> list[BlueprintManifest]:
        result: list[BlueprintManifest] = []
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or folder.name == "usage":
                continue
            if latest_only:
                try:
                    result.append(self.get(folder.name))
                except KeyError:
                    pass
                continue
            for version in sorted((item.name for item in folder.iterdir() if item.is_dir()), key=_version_key):
                try:
                    result.append(self.get(folder.name, version))
                except KeyError:
                    pass
        return result

    def record_usage(
        self,
        *,
        project_id: str,
        slug: str,
        version: str,
        score: float,
        outcome: str = "selected",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        path = self.root / "usage" / "events.jsonl"
        event = {
            "project_id": project_id,
            "slug": slug,
            "version": version,
            "score": score,
            "outcome": outcome,
            "metadata": metadata or {},
            "created_at": _now(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def metrics(self) -> dict[str, dict[str, Any]]:
        path = self.root / "usage" / "events.jsonl"
        result: dict[str, dict[str, Any]] = {}
        if not path.exists():
            return result
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            key = f"{event['slug']}@{event['version']}"
            item = result.setdefault(key, {"uses": 0, "successful": 0, "failed": 0, "score_total": 0.0})
            item["uses"] += 1
            item["score_total"] += float(event.get("score", 0))
            if event.get("outcome") in {"success", "completed"}:
                item["successful"] += 1
            if event.get("outcome") in {"failed", "error"}:
                item["failed"] += 1
        for item in result.values():
            item["average_score"] = round(item.pop("score_total") / max(1, item["uses"]), 4)
            item["success_rate"] = round(item["successful"] / max(1, item["uses"]), 4)
        return result
