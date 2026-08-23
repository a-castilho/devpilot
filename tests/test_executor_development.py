from types import SimpleNamespace

from app.services.executor import (
    DEVELOPMENT_DUPLICATE_GUARD,
    SYSTEM_DESIGN_GATE,
    development_prompt,
)


def test_development_prompt_starts_with_duplicate_preflight_before_changes():
    task = SimpleNamespace(title="Desenvolver menu", prompt="Adicione o menu solicitado.")
    prompt = development_prompt(task)
    assert "DUPLICATION PREFLIGHT" in DEVELOPMENT_DUPLICATE_GUARD
    assert "Do not create a parallel or second implementation" in prompt
    assert "If the feature already exists completely" in prompt
    assert prompt.index("DUPLICATION PREFLIGHT") < prompt.index("SYSTEM DESIGN GATE")


def test_development_prompt_requires_system_design_before_implementation():
    task = SimpleNamespace(
        title="Adicionar autenticação multi-tenant",
        prompt="Implemente autenticação com isolamento por tenant.",
    )
    prompt = development_prompt(task)

    assert "SYSTEM DESIGN GATE" in SYSTEM_DESIGN_GATE
    assert "Classify the requested change as SIMPLE or STRUCTURAL" in prompt
    assert "System Design dispensado" in prompt
    assert "authentication and authorization" in prompt
    assert "security and tenant isolation" in prompt
    assert "deployment strategy" in prompt
    assert "rollback" in prompt
    assert prompt.index("SYSTEM DESIGN GATE") < prompt.index("Only after completing both mandatory phases")
