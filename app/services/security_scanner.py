from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from app.models import Project
from app.services.executor import ensure_repository, run
from app.services.project_context import repository_commit

MAX_FILE_BYTES = 300_000
MAX_FILES = 2_500


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    category: str
    title: str
    file_path: str
    line_number: int
    evidence: str
    impact: str
    remediation: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str
    category: str
    title: str
    pattern: re.Pattern[str]
    impact: str
    remediation: str


_RULES = (
    Rule(
        "SEC001", "critical", "secrets", "Chave privada possivelmente versionada",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "Uma chave privada no repositório pode permitir acesso não autorizado mesmo após remover o arquivo do branch atual.",
        "Revogue/rotacione a chave, remova-a do histórico Git e use o Vault ou secret manager.",
    ),
    Rule(
        "SEC002", "high", "secrets", "Segredo possivelmente hard-coded",
        re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|access[_-]?token|password|passwd)\b\s*[:=]\s*[\"'][^\"']{10,}[\"']"),
        "Credenciais no código podem vazar por clone, logs, artefatos ou histórico Git.",
        "Mova o valor para o Vault/variável de ambiente, rotacione o segredo e mantenha somente a referência no código.",
    ),
    Rule(
        "SEC003", "high", "code-execution", "Subprocess com shell=True",
        re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^\n]*shell\s*=\s*True"),
        "Entradas não confiáveis podem alcançar um shell e virar injeção de comando.",
        "Use lista de argumentos, shell=False, diretório fixo, timeout e validação explícita.",
    ),
    Rule(
        "SEC004", "high", "code-execution", "Execução de comando via os.system",
        re.compile(r"\bos\.system\s*\("),
        "Concatenação de entrada em comandos pode permitir execução arbitrária no host.",
        "Substitua por subprocess com lista de argumentos, sem shell, timeout e cwd controlado.",
    ),
    Rule(
        "SEC005", "medium", "code-execution", "Uso de eval/exec",
        re.compile(r"(?<![A-Za-z0-9_])(?:eval|exec)\s*\("),
        "Conteúdo controlado pelo usuário pode ser interpretado como código.",
        "Remova avaliação dinâmica; use parser/dispatch explícito ou uma linguagem de regras restrita.",
    ),
    Rule(
        "SEC006", "medium", "web", "CORS liberado para qualquer origem",
        re.compile(r"allow_origins\s*=\s*\[\s*[\"']\*[\"']\s*\]"),
        "Qualquer origem web pode iniciar requisições cross-origin, ampliando a superfície de abuso.",
        "Restrinja CORS aos domínios necessários por ambiente e revise credenciais/cookies.",
    ),
    Rule(
        "SEC007", "medium", "configuration", "Modo debug habilitado no código",
        re.compile(r"\bdebug\s*=\s*True\b"),
        "Debug em produção pode expor detalhes internos, stack traces e configuração.",
        "Controle debug por configuração de ambiente e mantenha-o desabilitado em produção.",
    ),
    Rule(
        "SEC008", "high", "authentication", "Validação de assinatura JWT desabilitada",
        re.compile(r"(?i)(verify_signature[\"']?\s*[:=]\s*False|verify\s*=\s*False)"),
        "Tokens adulterados podem ser aceitos como autenticados.",
        "Mantenha verificação criptográfica ativa e valide algoritmo, emissor, audiência e expiração.",
    ),
    Rule(
        "SEC009", "high", "ci-cd", "Workflow com permissions: write-all",
        re.compile(r"(?im)^\s*permissions\s*:\s*write-all\s*$"),
        "Um workflow comprometido recebe permissões amplas sobre o repositório e outros recursos do GitHub.",
        "Defina permissões mínimas por workflow/job e eleve apenas o escopo necessário.",
    ),
    Rule(
        "SEC010", "medium", "ci-cd", "Uso de pull_request_target",
        re.compile(r"(?m)^\s*pull_request_target\s*:"),
        "Esse evento roda no contexto privilegiado do repositório base e exige cuidado especial com código de forks.",
        "Não execute código não confiável do PR nesse evento; separe validação de conteúdo e ações privilegiadas.",
    ),
)

_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md",
    ".txt", ".ini", ".cfg", ".sh", ".sql", ".html", ".css", ".scss", ".go", ".rs",
    ".java", ".kt", ".php", ".rb", ".cs", ".xml",
}
_SECRET_FILENAMES = re.compile(
    r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx)$|id_rsa$|id_ed25519$)", re.IGNORECASE
)
_DEPENDENCY_FILES = {
    "pyproject.toml", "requirements.txt", "requirements-dev.txt", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "Pipfile.lock", "go.mod", "Cargo.lock",
}


def _tracked_files(repository: Path) -> list[str]:
    result = run(["git", "ls-files"], cwd=repository, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to enumerate repository files")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()][:MAX_FILES]


def _evidence(line: str) -> str:
    clean = line.strip().replace("\t", " ")[:220]
    clean = re.sub(
        r"(?i)(api[_-]?key|client[_-]?secret|access[_-]?token|password|passwd)(\s*[:=]\s*)[\"'][^\"']+[\"']",
        r"\1\2\"[REDACTED]\"",
        clean,
    )
    return clean


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _docker_findings(path: str, text: str) -> list[Finding]:
    if PurePosixPath(path).name != "Dockerfile":
        return []
    has_user = bool(re.search(r"(?im)^\s*USER\s+\S+", text))
    if has_user:
        return []
    return [
        Finding(
            rule_id="SEC011",
            severity="medium",
            category="container",
            title="Container sem USER não-root explícito",
            file_path=path,
            line_number=1,
            evidence="Dockerfile sem diretiva USER",
            impact="A aplicação pode executar como root dentro do container, aumentando o impacto de uma exploração.",
            remediation="Crie usuário/grupo sem privilégios, ajuste ownership e finalize a imagem com USER não-root.",
        )
    ]


def scan_project(project: Project) -> dict:
    repository = ensure_repository(project)
    commit_sha = repository_commit(repository, project.default_branch)
    tracked = _tracked_files(repository)
    findings: list[Finding] = []
    scanned_files = 0
    skipped_large = 0
    dependency_manifests: list[str] = []

    for relative in tracked:
        if _SECRET_FILENAMES.search(relative):
            findings.append(
                Finding(
                    rule_id="SEC000",
                    severity="high",
                    category="secrets",
                    title="Arquivo sensível versionado",
                    file_path=relative,
                    line_number=1,
                    evidence="nome de arquivo sensível versionado",
                    impact="Segredos e configuração privada podem permanecer no histórico Git e ser distribuídos a qualquer clone.",
                    remediation="Remova do Git, adicione ao .gitignore e rotacione qualquer segredo que já tenha sido versionado.",
                )
            )
            continue

        name = PurePosixPath(relative).name
        if name in _DEPENDENCY_FILES:
            dependency_manifests.append(relative)

        suffix = PurePosixPath(relative).suffix.lower()
        if suffix not in _TEXT_SUFFIXES and name not in {"Dockerfile", "Makefile"}:
            continue
        target = repository / relative
        try:
            if not target.is_file():
                continue
            if target.stat().st_size > MAX_FILE_BYTES:
                skipped_large += 1
                continue
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        scanned_files += 1
        lines = text.splitlines()
        for rule in _RULES:
            for match in rule.pattern.finditer(text):
                line_no = _line_number(text, match.start())
                line = lines[line_no - 1] if lines and line_no <= len(lines) else ""
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        category=rule.category,
                        title=rule.title,
                        file_path=relative,
                        line_number=line_no,
                        evidence=_evidence(line),
                        impact=rule.impact,
                        remediation=rule.remediation,
                    )
                )
        findings.extend(_docker_findings(relative, text))

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(
        key=lambda item: (rank.get(item.severity, 9), item.file_path, item.line_number, item.rule_id)
    )
    counts = {severity: sum(1 for item in findings if item.severity == severity) for severity in rank}
    return {
        "commit_sha": commit_sha,
        "findings": [item.as_dict() for item in findings],
        "counts": counts,
        "coverage": {
            "tracked_files": len(tracked),
            "scanned_text_files": scanned_files,
            "skipped_large_files": skipped_large,
            "dependency_manifests": dependency_manifests,
            "dependency_vulnerability_database": "not-enabled",
        },
    }
