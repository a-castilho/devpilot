from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class BlueprintStatus(str, Enum):
    experimental = "experimental"
    candidate = "candidate"
    stable = "stable"
    deprecated = "deprecated"


@dataclass(frozen=True)
class BlueprintFile:
    path: str
    content: str
    executable: bool = False


@dataclass(frozen=True)
class BlueprintManifest:
    slug: str
    name: str
    version: str
    description: str = ""
    kind: str = "generic"
    status: BlueprintStatus = BlueprintStatus.experimental
    stack: dict[str, str] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    files: tuple[BlueprintFile, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["capabilities"] = list(self.capabilities)
        value["parameters"] = list(self.parameters)
        value["tags"] = list(self.tags)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BlueprintManifest":
        return cls(
            slug=str(value["slug"]),
            name=str(value["name"]),
            version=str(value["version"]),
            description=str(value.get("description", "")),
            kind=str(value.get("kind", "generic")),
            status=BlueprintStatus(value.get("status", BlueprintStatus.experimental.value)),
            stack={str(k): str(v) for k, v in dict(value.get("stack", {})).items()},
            capabilities=tuple(str(x) for x in value.get("capabilities", [])),
            parameters=tuple(str(x) for x in value.get("parameters", [])),
            files=tuple(BlueprintFile(**item) for item in value.get("files", [])),
            tags=tuple(str(x) for x in value.get("tags", [])),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class ProjectRequirements:
    description: str = ""
    stack: dict[str, str] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlueprintMatch:
    slug: str
    version: str
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderedProject:
    blueprint_slug: str
    blueprint_version: str
    files: dict[str, str]
    parameters: dict[str, str]
