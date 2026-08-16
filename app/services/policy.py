from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import get_settings


HIGH_RISK_WORDS = {
    "deploy",
    "produção",
    "production",
    "merge",
    "push",
    "delete",
    "deletar",
    "drop",
    "migrate",
    "migração",
    "dependency",
    "dependência",
}


@dataclass(frozen=True)
class PolicyDecision:
    requires_approval: bool
    reasons: tuple[str, ...]


def validate_repository_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Repository URL must use HTTPS")
    if parsed.hostname.lower() not in get_settings().git_hosts:
        raise ValueError(f"Git host is not allowed: {parsed.hostname}")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in repository URLs")


def evaluate_task(prompt: str, requested_approval: bool) -> PolicyDecision:
    lowered = prompt.lower()
    hits = tuple(sorted(word for word in HIGH_RISK_WORDS if word in lowered))
    return PolicyDecision(requires_approval=requested_approval or bool(hits), reasons=hits)
