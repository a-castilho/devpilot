from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


MAX_CV_BYTES = 4 * 1024 * 1024
LINKEDIN_HEADLINE_LIMIT = 220
LINKEDIN_ABOUT_LIMIT = 2600

_SECTION_ALIASES = {
    "resumo profissional": "about",
    "perfil profissional": "about",
    "sobre": "about",
    "competências-chave": "skills",
    "competencias-chave": "skills",
    "habilidades técnicas": "skills",
    "habilidades tecnicas": "skills",
    "experiência profissional": "experience",
    "experiencia profissional": "experience",
    "projetos recentes": "projects",
    "projetos": "projects",
    "formação": "education",
    "formacao": "education",
    "formação acadêmica": "education",
    "formacao academica": "education",
    "cursos & especializações": "courses",
    "cursos & especializacoes": "courses",
    "cursos e especializações": "courses",
    "cursos e especializacoes": "courses",
    "idiomas": "languages",
    "outras qualificações": "other",
    "outras qualificacoes": "other",
}

_ROLE_RE = re.compile(
    r"^(?P<company>[^|]{2,}?)\s*\|\s*(?P<title>[^|]{2,}?)\s*\|\s*(?P<period>.+)$"
)
_PROJECT_RE = re.compile(r"^(?P<name>[A-Za-zÀ-ÿ0-9][^—–:]{1,80})\s*[—–:]\s*(?P<description>.+)$")

_TECH_SKILLS = (
    "Python", "PHP", "Java", "JavaScript", "TypeScript", "C#", "FastAPI", "Django",
    "Flask", "Laravel", "Symfony", "Zend", "CakePHP", "Node.js", "React", "React.js",
    "Vue.js", "Inertia.js", "Livewire", "Next.js", "SQLAlchemy", "Pydantic", "Uvicorn",
    "PostgreSQL", "MySQL", "Oracle", "SQL Server", "Redis", "Elasticsearch", "Neon",
    "Docker", "Docker Compose", "Kubernetes", "AWS", "Serverless", "Terraform",
    "CloudFormation", "CI/CD", "Git", "GitHub", "REST APIs", "Microservices",
    "Microserviços", "DDD", "TDD", "SOLID", "Arquitetura Hexagonal",
    "Hexagonal Architecture", "OpenAI", "Gemini", "Codex", "Codex CLI", "LLMs",
    "AI Agents", "Agentes de IA", "SearXNG", "OpenAI Responses API", "Ollama",
    "Anthropic", "LangChain", "LlamaIndex", "RAG", "embeddings", "busca semântica",
    "structured outputs", "web search", "transcrição de voz", "Scrum", "Kanban",
    "Pentaho", "Pytest", "Requests", "Beautiful Soup", "RBAC", "Multi-tenancy",
    "WebSocket",
)


def source_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _collapse_spaces(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value).strip()


def _normalized_heading(value: str) -> str:
    return _collapse_spaces(value).strip(" :").casefold()


def _docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as error:
        raise ValueError("DOCX inválido ou corrompido") from error

    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        text = _collapse_spaces(text)
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_resume_text(filename: str, content: bytes) -> str:
    if not content:
        raise ValueError("Currículo vazio")
    if len(content) > MAX_CV_BYTES:
        raise ValueError("Currículo excede o limite de 4 MB")

    suffix = Path(filename or "resume.txt").suffix.casefold()
    if suffix == ".docx":
        text = _docx_text(content)
    elif suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Arquivo de texto deve estar em UTF-8") from error
    else:
        raise ValueError("Formato não suportado. Envie DOCX, TXT ou Markdown")

    normalized = "\n".join(_collapse_spaces(line) for line in text.splitlines() if line.strip())
    if len(normalized) < 40:
        raise ValueError("Não foi possível extrair conteúdo suficiente do currículo")
    return normalized


def _section_key(line: str) -> str | None:
    normalized = _normalized_heading(line)
    direct = _SECTION_ALIASES.get(normalized)
    if direct:
        return direct
    for heading, key in sorted(
        _SECTION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if normalized.startswith(f"{heading} |") or normalized.startswith(f"{heading} —"):
            return key
        if normalized.startswith(f"{heading} -") or normalized.startswith(f"{heading} ("):
            return key
    return None


def _split_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        key = _section_key(line)
        if key:
            current = key
            sections.setdefault(key, [])
            continue
        if current:
            sections[current].append(line)
        else:
            preamble.append(line)
    return preamble, sections


def _is_contact_line(value: str) -> bool:
    lowered = value.casefold()
    return (
        "linkedin.com/" in lowered
        or "@" in value
        or bool(re.search(r"\(?\d{2}\)?\s*\d{4,5}[- ]?\d{4}", value))
    )


def _detect_headline(preamble: list[str]) -> str:
    for line in preamble[1:6]:
        if _is_contact_line(line):
            continue
        if " | " in line or line.isupper():
            return line[:LINKEDIN_HEADLINE_LIMIT]
    return preamble[1][:LINKEDIN_HEADLINE_LIMIT] if len(preamble) > 1 else ""


def _extract_skills(text: str) -> list[str]:
    haystack = text.casefold()
    results: list[str] = []
    seen: set[str] = set()
    for skill in _TECH_SKILLS:
        variants = {skill.casefold()}
        if skill == "React":
            variants.add("react.js")
        if skill == "Microservices":
            variants.add("microserviços")
        if skill == "web search":
            variants.update({"web_search", "tool/web search"})
        if any(variant in haystack for variant in variants):
            key = skill.casefold()
            if key not in seen:
                seen.add(key)
                results.append(skill)
    return results[:100]


def _parse_experience(lines: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        cleaned = line.lstrip("•·- ").strip()
        match = _ROLE_RE.match(cleaned)
        if match:
            if current:
                items.append(current)
            current = {
                "company": _collapse_spaces(match.group("company")),
                "title": _collapse_spaces(match.group("title")),
                "period": _collapse_spaces(match.group("period")),
                "description": [],
            }
            continue
        if current:
            current["description"].append(cleaned)
    if current:
        items.append(current)
    for item in items:
        item["description"] = "\n".join(part for part in item["description"] if part)
    return items


def _parse_projects(lines: list[str]) -> list[dict[str, str]]:
    projects: list[dict[str, str]] = []
    for line in lines:
        cleaned = line.lstrip("•·- ").strip()
        match = _PROJECT_RE.match(cleaned)
        if match:
            projects.append(
                {
                    "name": _collapse_spaces(match.group("name")),
                    "description": _collapse_spaces(match.group("description")),
                }
            )
    return projects


def parse_resume(text: str) -> dict[str, Any]:
    lines = [_collapse_spaces(line) for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Currículo sem conteúdo")
    preamble, sections = _split_sections(lines)
    name = preamble[0] if preamble else lines[0]
    headline = _detect_headline(preamble)
    about = " ".join(sections.get("about", [])).strip()
    if not about:
        about = " ".join(line for line in preamble[1:] if not _is_contact_line(line)).strip()
    return {
        "name": name,
        "headline": headline[:LINKEDIN_HEADLINE_LIMIT],
        "about": about[:LINKEDIN_ABOUT_LIMIT],
        "skills": _extract_skills(text),
        "experience": _parse_experience(sections.get("experience", [])),
        "projects": _parse_projects(sections.get("projects", [])),
        "education": [line.lstrip("•·- ").strip() for line in sections.get("education", [])],
        "courses": [line.lstrip("•·- ").strip() for line in sections.get("courses", [])],
        "languages": [line.lstrip("•·- ").strip() for line in sections.get("languages", [])],
        "raw_sections": {key: "\n".join(value) for key, value in sections.items()},
    }


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return _collapse_spaces(value)
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    return value


def profile_diff(current: dict[str, Any] | None, desired: dict[str, Any]) -> list[dict[str, Any]]:
    current = current or {}
    changes: list[dict[str, Any]] = []
    fields = ("headline", "about", "experience", "skills", "projects", "education", "languages")
    for field in fields:
        before = current.get(field)
        after = desired.get(field)
        if _canonical_value(before) != _canonical_value(after):
            changes.append({"field": field, "before": before, "after": deepcopy(after)})
    return changes


def copy_package(profile: dict[str, Any]) -> dict[str, Any]:
    experience = []
    for item in profile.get("experience", []):
        header = " | ".join(
            part for part in (item.get("company"), item.get("title"), item.get("period")) if part
        )
        experience.append({"header": header, "description": item.get("description", "")})
    return {
        "headline": profile.get("headline", ""),
        "about": profile.get("about", ""),
        "skills": profile.get("skills", []),
        "experience": experience,
        "projects": profile.get("projects", []),
        "education": profile.get("education", []),
        "languages": profile.get("languages", []),
    }


def dumps_profile(profile: dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False, sort_keys=True)


def loads_profile(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
