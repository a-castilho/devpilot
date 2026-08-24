import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import get_settings


HIGH_RISK_WORDS = {
    "deploy",
    "implante",
    "implantar",
    "publicar",
    "publique",
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
    "sudo",
    "shutdown",
    "reboot",
    "chmod",
    "chown",
}

REPOSITORY_SHORTHAND = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
SSH_REPOSITORY = re.compile(r"^git@(?P<host>[^:]+):(?P<path>[^\s]+)$")
_REPOSITORY_WRAPPERS = {"`": "`", '"': '"', "'": "'", "<": ">"}


@dataclass(frozen=True)
class PolicyDecision:
    requires_approval: bool
    reasons: tuple[str, ...]


def _clean_repository_input(value: str) -> str:
    raw = str(value or "")
    raw = raw.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    raw = raw.replace("\ufeff", "").replace("\u00a0", " ").strip()

    changed = True
    while changed and len(raw) >= 2:
        changed = False
        closing = _REPOSITORY_WRAPPERS.get(raw[0])
        if closing and raw[-1] == closing:
            raw = raw[1:-1].strip()
            changed = True

    # Mobile copy/paste frequently inserts spaces around `/`.
    raw = re.sub(r"\s*/\s*", "/", raw)
    return raw.strip()


def normalize_repository_url(url: str) -> str:
    raw = _clean_repository_input(url)
    if not raw:
        raise ValueError("Informe o repositório no formato organização/repositório.")

    shorthand = REPOSITORY_SHORTHAND.fullmatch(raw)
    if shorthand:
        raw = f"https://github.com/{shorthand.group('owner')}/{shorthand.group('repo')}"
    elif raw.lower().startswith("github.com/"):
        raw = f"https://{raw}"
    elif raw.lower().startswith("www.github.com/"):
        raw = f"https://{raw[4:]}"
    else:
        ssh = SSH_REPOSITORY.fullmatch(raw)
        if ssh:
            raw = f"https://{ssh.group('host')}/{ssh.group('path')}"

    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Informe o repositório no formato organização/repositório.")

    hostname = parsed.hostname.lower()
    if hostname == "www.github.com":
        hostname = "github.com"

    if hostname not in get_settings().git_hosts:
        raise ValueError(f"Host Git não permitido: {hostname}")
    if parsed.username or parsed.password:
        raise ValueError("Não inclua usuário, senha ou token na URL do repositório.")
    if parsed.query or parsed.fragment:
        raise ValueError("A URL do repositório não pode conter parâmetros ou fragmentos.")

    path = parsed.path.strip("/")
    parts = path.split("/") if path else []
    if len(parts) != 2 or any(part in {".", "..", ""} for part in parts):
        raise ValueError("Informe o repositório no formato organização/repositório.")

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise ValueError("Informe o repositório no formato organização/repositório.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", repo
    ):
        raise ValueError("Informe o repositório no formato organização/repositório.")

    return f"https://{hostname}/{owner}/{repo}.git"


def validate_repository_url(url: str) -> None:
    normalize_repository_url(url)


def evaluate_task(prompt: str, requested_approval: bool) -> PolicyDecision:
    lowered = prompt.lower()
    hits = tuple(sorted(word for word in HIGH_RISK_WORDS if word in lowered))
    return PolicyDecision(requires_approval=requested_approval or bool(hits), reasons=hits)
