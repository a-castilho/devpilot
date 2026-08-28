import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import get_settings


HIGH_RISK_PATTERNS = (
    (
        "push",
        re.compile(r"\b(?:git\s+)?push\b|\bforce[- ]?push\b", re.IGNORECASE),
    ),
    (
        "merge",
        re.compile(r"\bmerge\b|\bmescl(?:ar|e|agem)\b", re.IGNORECASE),
    ),
    (
        "deploy",
        re.compile(r"\bdeploy(?:ment)?\b|\bpublic(?:ar|ação)\b", re.IGNORECASE),
    ),
    (
        "production",
        re.compile(r"\bproduç(?:ão|ao)\b|\bproduction\b|\bprod\b", re.IGNORECASE),
    ),
    (
        "dependency",
        re.compile(
            r"\bdepend(?:ency|encies|ência|encias)\b|"
            r"\b(?:pip|npm|pnpm|yarn|composer)\s+(?:install|add|remove|update|upgrade)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "destructive",
        re.compile(
            r"\b(?:delete|deletar|apagar|drop|truncate)\b|"
            r"\breset\s+--hard\b|\brm\s+-rf\b|\bforce[- ]?push\b",
            re.IGNORECASE,
        ),
    ),
    (
        "destructive-migration",
        re.compile(
            r"\b(?:migration|migrate|migraç(?:ão|ao))\b[^\n]{0,80}"
            r"\b(?:drop|delete|truncate|destrutiv|irrevers)\w*\b|"
            r"\b(?:drop|delete|truncate|destrutiv|irrevers)\w*\b[^\n]{0,80}"
            r"\b(?:migration|migrate|migraç(?:ão|ao))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential",
        re.compile(
            r"\b(?:secret|secrets|segredo|segredos|credential|credentials|credencial|credenciais|"
            r"api[-_ ]?key|token|password|senha)\b[^\n]{0,60}"
            r"\b(?:alter|trocar|rotate|rotacion|revog|delet|apag|exclu|expor|mostrar|print)\w*\b|"
            r"\b(?:alter|trocar|rotate|rotacion|revog|delet|apag|exclu|expor|mostrar|print)\w*\b"
            r"[^\n]{0,60}\b(?:secret|secrets|segredo|segredos|credential|credentials|credencial|"
            r"credenciais|api[-_ ]?key|token|password|senha)\b",
            re.IGNORECASE,
        ),
    ),
)

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


def evaluate_task(prompt: str, requested_approval: bool = False) -> PolicyDecision:
    """Apply approval-by-exception to a task.

    Local, auditable and reversible work is pre-authorized. Explicit user opt-in or
    any high-risk boundary still requires approval before execution.
    """
    reasons = tuple(
        name for name, pattern in HIGH_RISK_PATTERNS if pattern.search(str(prompt or ""))
    )
    return PolicyDecision(
        requires_approval=bool(requested_approval or reasons),
        reasons=reasons,
    )
