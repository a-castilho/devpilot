import re


PROJECT_PATTERNS = (r"projeto\s+([\w.-]+)", r"no\s+([\w.-]+)")


def interpret_voice(transcript: str) -> dict:
    cleaned = " ".join(transcript.strip().split())
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
