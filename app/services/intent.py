import re

from app.services.organizations import project_slug


PROJECT_PATTERNS = (r"projeto\s+([\w.-]+)", r"no\s+([\w.-]+)")
PROJECT_START_PATTERNS = (
    r"^(?:iniciar|inicie|criar|crie|come[cç]ar|comece)\s+(?:um\s+)?(?:novo\s+)?projeto(?:\s+(?:chamado|nomeado)\s+)?(?P<name>.*)$",
    r"^novo\s+projeto(?:\s+(?P<name>.*))?$",
)


def project_start_intent(transcript: str) -> dict | None:
    cleaned = " ".join(transcript.strip().split())
    for pattern in PROJECT_START_PATTERNS:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        name = str(match.groupdict().get("name") or "").strip(" .:-")
        return {
            "title": f"Iniciar projeto {name}".strip(),
            "prompt": cleaned,
            "project_hint": None,
            "project_name": name,
            "project_slug": project_slug(name) if name else "",
            "action": "start_project",
            "requires_authorization": True,
        }
    return None


def interpret_voice(transcript: str) -> dict:
    cleaned = " ".join(transcript.strip().split())
    if start := project_start_intent(cleaned):
        return start

    lowered = cleaned.lower()
    project_hint = None
    for pattern in PROJECT_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            project_hint = match.group(1)
            break
    action = "analyze" if any(word in lowered for word in ("analise", "analisar", "audite")) else "develop"
    title = cleaned[:100] + ("…" if len(cleaned) > 100 else "")
    return {"title": title, "prompt": cleaned, "project_hint": project_hint, "action": action}
