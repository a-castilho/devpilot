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
        re.compile(
            r"\b(?:ambiente|servidor|cluster|banco|database|sistema)\s+(?:de|em)\s+produç(?:ão|ao)\b|"
            r"\b(?:em|para|no|na)\s+(?:produç(?:ão|ao)|production|prod)\b|"
            r"\b(?:production|prod)\s+(?:environment|env|server|cluster|database)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "dependency",
        re.compile(
            r"\b(?:depend(?:ency|encies|ência|ências|encias))\b[^\n]{0,70}"
            r"\b(?:install|add|remove|update|upgrade|instalar|adicionar|remover|atualizar|alterar)\w*\b|"
            r"\b(?:install|add|remove|update|upgrade|instalar|adicionar|remover|atualizar|alterar)\w*\b"
            r"[^\n]{0,70}\b(?:depend(?:ency|encies|ência|ências|encias))\b|"
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

_NEGATION = re.compile(
    r"\b(?:não|nao|nunca|jamais|never|do\s+not|don't|must\s+not|proibid[oa])\b",
    re.IGNORECASE,
)
_NEGATION_EXCEPTIONS = re.compile(
    r"\b(?:não|nao)\s+(?:deixe\s+de|esqueça\s+de|esqueca\s+de)|"
    r"\bdo\s+not\s+forget\s+to\b",
    re.IGNORECASE,
)
_READ_ONLY_CUES = re.compile(
    r"\b(?:verifique|verificar|valide|validar|confirme|confirmar|revise|revisar|inspecione|inspecionar|"
    r"audite|auditar|detecte|detectar|documente|documentar|check|verify|validate|confirm|review|inspect|audit)\b",
    re.IGNORECASE,
)
_MUTATING_CUES = re.compile(
    r"\b(?:faça|faca|fazer|execute|executar|rode|rodar|publique|publicar|envie|enviar|aplique|aplicar|"
    r"crie|criar|implemente|implementar|configure|configurar|provisione|provisionar|instale|instalar|"
    r"adicione|adicionar|remova|remover|atualize|atualizar|altere|alterar|apague|apagar|delete|deletar|"
    r"drop|truncate|mescle|mesclar|force|forçar|forcar)\b",
    re.IGNORECASE,
)
_NEGATED_MUTATION = re.compile(
    r"\b(?:sem|without)\s+(?:alterar|atualizar|remover|instalar|adicionar|publicar|executar|fazer|"
    r"change|update|remove|install|add|publish|deploy)\w*\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT = re.compile(r"(?:[.;]\s+|;\s*)")

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


def _is_negated_match(clause: str, start: int) -> bool:
    prefix = str(clause or "")[max(0, start - 72):start]
    if _NEGATION_EXCEPTIONS.search(prefix):
        return False
    matches = list(_NEGATION.finditer(prefix))
    if not matches:
        return False
    last = matches[-1]
    tail = prefix[last.end():]
    return not re.search(r"[.;:]", tail)


def _is_read_only_clause(clause: str) -> bool:
    return bool(_READ_ONLY_CUES.search(clause) and not _MUTATING_CUES.search(clause))


def _clauses(text: str):
    for raw_line in str(text or "").splitlines() or [str(text or "")]:
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in _CLAUSE_SPLIT.split(line) if part.strip()]
        for part in parts or [line]:
            yield part


def _has_actionable_match(text: str, pattern: re.Pattern[str]) -> bool:
    for clause in _clauses(text):
        read_only = _is_read_only_clause(clause)
        for match in pattern.finditer(clause):
            if _is_negated_match(clause, match.start()):
                continue
            matched_text = match.group(0)
            if _NEGATED_MUTATION.search(matched_text):
                continue
            if read_only:
                continue
            return True
    return False


def evaluate_task(prompt: str, requested_approval: bool = False) -> PolicyDecision:
    """Apply approval-by-exception using requested actions, not safety prose.

    Local, auditable and reversible work is pre-authorized. Explicit user opt-in or
    any high-risk action still requires approval. Guardrails such as "never force
    push" and read-only checks such as "verify the configured deployment" must not
    create a false authorization gate simply because they mention a risky concept.
    """
    text = str(prompt or "")
    reasons = tuple(
        name for name, pattern in HIGH_RISK_PATTERNS if _has_actionable_match(text, pattern)
    )
    return PolicyDecision(
        requires_approval=bool(requested_approval or reasons),
        reasons=reasons,
    )
