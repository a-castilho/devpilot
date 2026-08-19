import re
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

REPOSITORY_SHORTHAND = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
SSH_REPOSITORY = re.compile(r"^git@(?P<host>[^:]+):(?P<path>[^\s]+)$")


@dataclass(frozen=True)
class PolicyDecision:
    requires_approval: bool
    reasons: tuple[str, ...]


def normalize_repository_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValueError("Repository URL is required")

    shorthand = REPOSITORY_SHORTHAND.fullmatch(raw)
    if shorthand:
        raw = f"https://github.com/{shorthand.group('owner')}/{shorthand.group('repo')}"
    elif raw.lower().startswith("github.com/"):
        raw = f"https://{raw}"
    else:
        ssh = SSH_REPOSITORY.fullmatch(raw)
        if ssh:
            raw = f"https://{ssh.group('host')}/{ssh.group('path')}"

    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(
            "Repository must be owner/repo, github.com/owner/repo, an HTTPS URL, or git@host:owner/repo"
        )
    if parsed.hostname.lower() not in get_settings().git_hosts:
        raise ValueError(f"Git host is not allowed: {parsed.hostname}")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in repository URLs")
    if parsed.query or parsed.fragment:
        raise ValueError("Repository URL must not contain query parameters or fragments")

    path = parsed.path.strip("/")
    parts = path.split("/") if path else []
    if len(parts) != 2 or any(part in {".", "..", ""} for part in parts):
        raise ValueError("Repository URL must identify exactly one owner/repository pair")

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise ValueError("Repository URL must identify a repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", repo
    ):
        raise ValueError("Repository owner and name contain unsupported characters")

    return f"https://{parsed.hostname.lower()}/{owner}/{repo}.git"


def validate_repository_url(url: str) -> None:
    normalize_repository_url(url)


def evaluate_task(prompt: str, requested_approval: bool) -> PolicyDecision:
    lowered = prompt.lower()
    hits = tuple(sorted(word for word in HIGH_RISK_WORDS if word in lowered))
    return PolicyDecision(requires_approval=requested_approval or bool(hits), reasons=hits)
