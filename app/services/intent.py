import re

from app.services.organizations import project_slug


PROJECT_PATTERNS = (r"projeto\s+([\w.-]+)", r"no\s+([\w.-]+)")
PROJECT_START_PATTERNS = (
    r"^(?:iniciar|inicie|criar|crie|come[cç]ar|comece)\s+(?:um\s+)?(?:novo\s+)?projeto(?:\s+(?:chamado|nomeado)\s+)?(?P<name>.*)$",
    r"^novo\s+projeto(?:\s+(?P<name>.*))?$",
)
LOCAL_UPDATE_PATTERNS = (
    r"^(?:atualizar|atualize|atualiza|sincronizar|sincronize)\s+(?:o\s+)?(?:devpilot\s+)?local(?:\s+(?:no\s+)?linux)?$",
    r"^(?:atualizar|atualize|atualiza)\s+(?:o\s+)?linux(?:\s+local)?$",
)

DEPLOY_WORDS = (
    "deploy",
    "implante",
    "implantar",
    "publique",
    "publicar",
    "produção",
    "production",
)
EXECUTION_WORDS = (
    "corrija",
    "corrigir",
    "implemente",
    "implementar",
    "desenvolva",
    "desenvolver",
    "execute",
    "executar",
    "aplique",
    "aplicar",
    "ajuste",
    "ajustar",
    "conserte",
    "consertar",
    "rode",
    "rodar",
    "reinicie",
    "reiniciar",
)
TEST_WORDS = (
    "teste",
    "testar",
    "valide",
    "validar",
    "homologue",
    "homologar",
)
ANALYSIS_WORDS = (
    "analise",
    "analisar",
    "audite",
    "auditar",
    "revise",
    "revisar",
    "verifique",
    "verificar",
)


def _contains_any(value: str, words: tuple[str, ...]) -> bool:
    return any(word in value for word in words)


def local_update_intent(transcript: str) -> dict | None:
    cleaned = " ".join(transcript.strip().split())
    if not any(re.match(pattern, cleaned, flags=re.IGNORECASE) for pattern in LOCAL_UPDATE_PATTERNS):
        return None
    return {
        "title": "Atualizar DevPilot local no Linux",
        "prompt": cleaned,
        "project_hint": None,
        "action": "update_local",
        "requires_authorization": False,
        "system_action": True,
        "operational": True,
    }


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
            "operational": True,
        }
    return None


def interpret_voice(transcript: str) -> dict:
    cleaned = " ".join(transcript.strip().split())
    if update := local_update_intent(cleaned):
        return update
    if start := project_start_intent(cleaned):
        return start

    lowered = cleaned.lower()
    project_hint = None
    for pattern in PROJECT_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            project_hint = match.group(1)
            break

    if _contains_any(lowered, DEPLOY_WORDS):
        action = "deploy"
        operational = True
    elif _contains_any(lowered, EXECUTION_WORDS):
        action = "develop"
        operational = True
    elif _contains_any(lowered, TEST_WORDS):
        action = "test"
        operational = True
    elif _contains_any(lowered, ANALYSIS_WORDS):
        action = "analyze"
        operational = True
    else:
        action = "develop"
        operational = False

    title = cleaned[:100] + ("…" if len(cleaned) > 100 else "")
    return {
        "title": title,
        "prompt": cleaned,
        "project_hint": project_hint,
        "action": action,
        "operational": operational,
    }
