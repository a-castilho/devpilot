from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
TOKEN_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
SECRET_RE = re.compile(
    r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|(?:password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^${{\s][^\s'\"]{7,})"
)
ALLOWED_STATUS = {"experimental", "candidate", "stable", "deprecated"}
STATUS_WEIGHT = {"stable": 12.0, "candidate": 7.0, "experimental": 2.0, "deprecated": -25.0}


class BlueprintError(ValueError):
    pass


@dataclass(frozen=True)
class Match:
    name: str
    version: str
    score: float
    reasons: list[str]


class BlueprintRegistry:
    """Filesystem registry with immutable versions and deterministic matching."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_manifest(manifest: dict[str, Any]) -> None:
        name = str(manifest.get("name", ""))
        version = str(manifest.get("version", ""))
        status = str(manifest.get("status", "experimental"))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}", name):
            raise BlueprintError("Nome de blueprint inválido")
        if not VERSION_RE.fullmatch(version):
            raise BlueprintError("Versão deve usar MAJOR.MINOR.PATCH")
        if status not in ALLOWED_STATUS:
            raise BlueprintError("Status de blueprint inválido")
        files = manifest.get("files", {})
        if not isinstance(files, dict) or not files:
            raise BlueprintError("Blueprint precisa declarar files")
        parameters = manifest.get("parameters", [])
        if not isinstance(parameters, list) or any(not isinstance(x, str) for x in parameters):
            raise BlueprintError("parameters inválido")
        declared = set(parameters)
        for raw_path, content in files.items():
            path = Path(str(raw_path))
            if path.is_absolute() or ".." in path.parts:
                raise BlueprintError(f"Caminho inseguro: {raw_path}")
            if not isinstance(content, str):
                raise BlueprintError(f"Conteúdo não textual: {raw_path}")
            if SECRET_RE.search(content):
                raise BlueprintError(f"Possível secret detectado: {raw_path}")
            missing = set(TOKEN_RE.findall(content)) - declared
            if missing:
                raise BlueprintError(f"Parâmetros não declarados em {raw_path}: {sorted(missing)}")

    def _path(self, name: str, version: str) -> Path:
        return self.root / name / version / "manifest.json"

    def register(self, manifest: dict[str, Any]) -> dict[str, Any]:
        self.validate_manifest(manifest)
        path = self._path(manifest["name"], manifest["version"])
        if path.exists():
            raise BlueprintError("Versão de blueprint já existe e é imutável")
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = dict(manifest)
        normalized.setdefault("status", "experimental")
        normalized.setdefault("stack", {})
        normalized.setdefault("capabilities", [])
        normalized.setdefault("validation", [])
        normalized.setdefault("metrics", {"uses": 0, "successes": 0, "failures": 0})
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2)
        if SECRET_RE.search(payload):
            raise BlueprintError("Possível secret detectado no manifest")
        path.write_text(payload + "\n", encoding="utf-8")
        return self.describe(normalized)

    def manifests(self) -> list[dict[str, Any]]:
        result = []
        for path in sorted(self.root.glob("*/*/manifest.json")):
            try:
                result.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return result

    @staticmethod
    def describe(manifest: dict[str, Any]) -> dict[str, Any]:
        clean = {k: v for k, v in manifest.items() if k != "files"}
        clean["file_count"] = len(manifest.get("files", {}))
        return clean

    def list(self) -> list[dict[str, Any]]:
        return [self.describe(m) for m in self.manifests()]

    def get(self, name: str, version: str) -> dict[str, Any]:
        path = self._path(name, version)
        if not path.exists():
            raise BlueprintError("Blueprint não encontrado")
        return json.loads(path.read_text(encoding="utf-8"))

    def match(self, *, stack: dict[str, str], capabilities: list[str], project_type: str = "") -> list[Match]:
        wanted_caps = {x.lower() for x in capabilities}
        wanted_stack = {str(k).lower(): str(v).lower() for k, v in stack.items()}
        matches: list[Match] = []
        for item in self.manifests():
            score = STATUS_WEIGHT.get(item.get("status", "experimental"), 0.0)
            reasons: list[str] = []
            item_stack = {str(k).lower(): str(v).lower() for k, v in item.get("stack", {}).items()}
            if wanted_stack:
                hits = sum(1 for k, v in wanted_stack.items() if item_stack.get(k) == v)
                score += 45.0 * hits / len(wanted_stack)
                reasons.append(f"stack {hits}/{len(wanted_stack)}")
            item_caps = {str(x).lower() for x in item.get("capabilities", [])}
            if wanted_caps:
                hits = len(wanted_caps & item_caps)
                score += 30.0 * hits / len(wanted_caps)
                reasons.append(f"capacidades {hits}/{len(wanted_caps)}")
            if project_type and str(item.get("type", "")).lower() == project_type.lower():
                score += 8.0
                reasons.append("tipo compatível")
            metrics = item.get("metrics", {})
            uses = int(metrics.get("uses", 0) or 0)
            successes = int(metrics.get("successes", 0) or 0)
            if uses:
                score += min(5.0, 5.0 * successes / uses)
                reasons.append("histórico validado")
            matches.append(Match(item["name"], item["version"], round(max(0.0, min(100.0, score)), 2), reasons))
        return sorted(matches, key=lambda x: (-x.score, x.name, x.version))

    def materialize(self, name: str, version: str, destination: Path, parameters: dict[str, str], *, overwrite: bool = False) -> dict[str, Any]:
        manifest = self.get(name, version)
        declared = set(manifest.get("parameters", []))
        missing = declared - set(parameters)
        if missing:
            raise BlueprintError(f"Parâmetros obrigatórios ausentes: {sorted(missing)}")
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        created: list[str] = []
        for raw_path, template in manifest["files"].items():
            relative = Path(raw_path)
            target = (destination / relative).resolve()
            if destination != target and destination not in target.parents:
                raise BlueprintError(f"Destino inseguro: {raw_path}")
            if target.exists() and not overwrite:
                raise BlueprintError(f"Arquivo já existe: {raw_path}")
            rendered = TOKEN_RE.sub(lambda m: str(parameters[m.group(1)]), template)
            if SECRET_RE.search(rendered):
                raise BlueprintError(f"Possível secret no arquivo renderizado: {raw_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            created.append(str(relative))
        fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return {"blueprint": name, "version": version, "files": created, "fingerprint": fingerprint}

    def record_outcome(self, name: str, version: str, success: bool) -> dict[str, Any]:
        path = self._path(name, version)
        manifest = self.get(name, version)
        metrics = dict(manifest.get("metrics", {}))
        metrics["uses"] = int(metrics.get("uses", 0) or 0) + 1
        key = "successes" if success else "failures"
        metrics[key] = int(metrics.get(key, 0) or 0) + 1
        manifest["metrics"] = metrics
        path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return metrics
