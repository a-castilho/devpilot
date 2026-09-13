from __future__ import annotations

import re

from .domain import BlueprintManifest, BlueprintMatch, BlueprintStatus, ProjectRequirements

_STATUS_WEIGHT = {
    BlueprintStatus.stable: 1.0,
    BlueprintStatus.candidate: 0.75,
    BlueprintStatus.experimental: 0.45,
    BlueprintStatus.deprecated: 0.05,
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#.-]+", value.lower()) if len(token) > 1}


def match_blueprints(
    requirements: ProjectRequirements,
    manifests: list[BlueprintManifest],
    *,
    minimum_score: float = 0.35,
) -> list[BlueprintMatch]:
    wanted_caps = {item.lower() for item in requirements.capabilities}
    wanted_tags = {item.lower() for item in requirements.tags}
    wanted_text = _tokens(requirements.description)
    results: list[BlueprintMatch] = []

    for manifest in manifests:
        if manifest.status is BlueprintStatus.deprecated:
            continue

        reasons: list[str] = []
        stack_hits = 0
        for key, expected in requirements.stack.items():
            actual = manifest.stack.get(key)
            if actual and actual.lower() == expected.lower():
                stack_hits += 1
        stack_score = stack_hits / max(1, len(requirements.stack))
        if stack_hits:
            reasons.append(f"stack {stack_hits}/{len(requirements.stack)}")

        manifest_caps = {item.lower() for item in manifest.capabilities}
        cap_hits = len(wanted_caps & manifest_caps)
        cap_score = cap_hits / max(1, len(wanted_caps))
        if cap_hits:
            reasons.append(f"capabilities {cap_hits}/{len(wanted_caps)}")

        manifest_tags = {item.lower() for item in manifest.tags}
        tag_hits = len(wanted_tags & manifest_tags)
        tag_score = tag_hits / max(1, len(wanted_tags))

        searchable = " ".join(
            [manifest.name, manifest.description, manifest.kind, *manifest.tags, *manifest.capabilities]
        )
        searchable_tokens = _tokens(searchable)
        text_hits = len(wanted_text & searchable_tokens)
        text_score = text_hits / max(1, min(len(wanted_text), 12))

        status_score = _STATUS_WEIGHT[manifest.status]
        score = (
            stack_score * 0.35
            + cap_score * 0.30
            + text_score * 0.15
            + tag_score * 0.10
            + status_score * 0.10
        )
        if not requirements.stack and not wanted_caps and not wanted_tags and not wanted_text:
            score = status_score * 0.10

        if score >= minimum_score:
            reasons.append(f"maturity {manifest.status.value}")
            results.append(
                BlueprintMatch(
                    slug=manifest.slug,
                    version=manifest.version,
                    score=round(score, 4),
                    reasons=tuple(reasons),
                )
            )

    return sorted(results, key=lambda item: item.score, reverse=True)
