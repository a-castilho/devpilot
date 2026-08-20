from types import SimpleNamespace

from app.services.executor import DEVELOPMENT_DUPLICATE_GUARD, development_prompt


def test_development_prompt_starts_with_duplicate_preflight_before_changes():
    task = SimpleNamespace(title="Desenvolver menu", prompt="Adicione o menu solicitado.")
    prompt = development_prompt(task)
    assert "DUPLICATION PREFLIGHT" in DEVELOPMENT_DUPLICATE_GUARD
    assert "Do not create a parallel or second implementation" in prompt
    assert "If the feature already exists completely" in prompt
    assert prompt.index("DUPLICATION PREFLIGHT") < prompt.index("Only after completing that preflight")
