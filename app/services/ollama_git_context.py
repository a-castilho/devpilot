from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project
from app.services.executor import ensure_repository, run
from app.services.git_reader import repository_ref


MAX_CONTEXT_CHARS = 7_000
MAX_FILE_SNIPPET_CHARS = 1_600
MAX_FILES = 4
MAX_TREE_FILES = 8_000
MAX_QUERY_TERMS = 5

_REPOSITORY_PATTERN = re.compile(
    r"Repositório:\s*(?P<url>\S+?)\.\s+Branch padrão:",
    re.IGNORECASE,
)
_WORD_PATTERN = re.compile(r"[A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ0-9_.-]{3,}")
_STOPWORDS = {
    "acessar",
    "agora",
    "ainda",
    "chat",
    "como",
    "deve",
    "devpilot",
    "local",
    "mais",
    "para",
    "pela",
    "pelo",
    "projeto",
    "selecionado",
    "sobre",
    "usar",
    "with",
    "from",
    "this",
    "that",
    "project",
}
_BLOCKED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}
_BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".sqlite",
    ".db",
    ".pyc",
}
_SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.json",
    "secrets.yml",
    "secrets.yaml",
}


def repository_url_from_input(input_text: str) -> str:
    match = _REPOSITORY_PATTERN.search(input_text or "")
    return match.group("url").strip() if match else ""


def _latest_client_text(input_text: str) -> str:
    marker = "\nCLIENTE:"
    if marker not in input_text:
        return input_text[-4_000:]
    value = input_text.rsplit(marker, 1)[-1]
    return value.partition("\nDEVPILOT:")[0].strip()


def _query_terms(input_text: str) -> list[str]:
    result: list[str] = []
    for raw in _WORD_PATTERN.findall(_latest_client_text(input_text)):
        value = raw.casefold().strip("._-")
        if len(value) < 4 or value in _STOPWORDS or value in result:
            continue
        result.append(value)
        if len(result) >= MAX_QUERY_TERMS:
            break
    return result


def _safe_text_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    lowered_parts = [part.casefold() for part in parts]
    if any(part in _BLOCKED_DIRS for part in lowered_parts):
        return False

    name = lowered_parts[-1]
    if name in _SENSITIVE_NAMES or name.startswith(".env."):
        return False
    if name.endswith((".pem", ".key", ".p12", ".pfx")):
        return False
    if name.startswith(("credentials.", "secrets.")):
        return False
    return Path(name).suffix.casefold() not in _BINARY_SUFFIXES


def _git(path: Path, args: list[str], *, timeout: int = 20) -> str:
    result = run(["git", *args], cwd=path, timeout=timeout)
    if result.returncode:
        return ""
    return result.stdout.strip()


def _tree_files(path: Path, ref: str) -> list[str]:
    output = _git(path, ["ls-tree", "-r", "--name-only", ref])
    result: list[str] = []
    for line in output.splitlines():
        file_path = line.strip()
        if file_path and _safe_text_path(file_path):
            result.append(file_path)
            if len(result) >= MAX_TREE_FILES:
                break
    return result


def _grep_paths(path: Path, ref: str, terms: list[str]) -> list[str]:
    matches: list[str] = []
    prefix = f"{ref}:"
    for term in terms:
        output = _git(path, ["grep", "-l", "-I", "-i", "-F", "-e", term, ref, "--"], timeout=15)
        for line in output.splitlines():
            file_path = line[len(prefix):] if line.startswith(prefix) else line
            file_path = file_path.strip()
            if _safe_text_path(file_path) and file_path not in matches:
                matches.append(file_path)
                if len(matches) >= 20:
                    return matches
    return matches


def _rank_files(files: list[str], grep_matches: list[str], terms: list[str]) -> list[str]:
    grep_set = set(grep_matches)
    priorities = {
        "AGENTS.md": 120,
        "README.md": 45,
        "pyproject.toml": 35,
        "package.json": 35,
        "composer.json": 35,
        "docker-compose.yml": 30,
        "docker-compose.yaml": 30,
    }
    ranked: list[tuple[int, str]] = []
    for file_path in files:
        score = priorities.get(file_path, 0)
        lowered = file_path.casefold()
        if file_path in grep_set:
            score += 90
        score += sum(18 for term in terms if term in lowered)
        if score:
            ranked.append((score, file_path))
    ranked.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return [file_path for _, file_path in ranked[:MAX_FILES]]


def _file_snippet(path: Path, ref: str, file_path: str) -> str:
    content = _git(path, ["show", f"{ref}:{file_path}"], timeout=20)
    if not content:
        return ""
    return content[:MAX_FILE_SNIPPET_CHARS].rstrip()


def _build_context_for_project(project: Project, input_text: str) -> str:
    repository = ensure_repository(project)
    ref = repository_ref(project)
    terms = _query_terms(input_text)
    files = _tree_files(repository, ref)
    grep_matches = _grep_paths(repository, ref, terms)
    selected_files = _rank_files(files, grep_matches, terms)

    status = _git(repository, ["status", "--short", "--branch"], timeout=10)
    recent = _git(
        repository,
        [
            "log",
            "-n",
            "6",
            "--date=short",
            "--pretty=format:%h %ad %s",
            ref,
            "--",
        ],
        timeout=15,
    )

    sections = [
        "CONTEXTO GIT SOMENTE LEITURA DO PROJETO SELECIONADO",
        f"Repositório: {project.repository_url}",
        f"Ref lida: {ref}",
    ]
    if status:
        sections.append(f"Status local:\n{status[:900]}")
    if recent:
        sections.append(f"Commits recentes:\n{recent[:1_500]}")
    if terms:
        sections.append("Termos usados para localizar código relevante: " + ", ".join(terms))

    for file_path in selected_files:
        snippet = _file_snippet(repository, ref, file_path)
        if snippet:
            sections.append(f"ARQUIVO {file_path}\n{snippet}")

    context = "\n\n".join(sections)
    return context[:MAX_CONTEXT_CHARS]


def build_ollama_git_context(input_text: str) -> str:
    """Return a compact, read-only Git snapshot for the project selected in Chat DevPilot."""
    repository_url = repository_url_from_input(input_text)
    if not repository_url:
        return ""

    with SessionLocal() as db:
        project = db.scalar(
            select(Project)
            .where(Project.repository_url == repository_url)
            .order_by(Project.created_at.desc())
        )
        if not project:
            return (
                "CONTEXTO GIT INDISPONÍVEL: o repositório do projeto selecionado não foi localizado "
                "no cadastro do DevPilot. Não afirme que arquivos foram lidos."
            )
        try:
            return _build_context_for_project(project, input_text)
        except Exception:
            return (
                "CONTEXTO GIT INDISPONÍVEL: não foi possível sincronizar ou ler o Git do projeto "
                "selecionado. Não afirme que arquivos foram lidos."
            )
