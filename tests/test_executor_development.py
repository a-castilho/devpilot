from pathlib import Path
from types import SimpleNamespace

from app.services.executor import (
    DEVELOPMENT_DUPLICATE_GUARD,
    build_generated_agents_md,
    development_prompt,
    write_generated_agents_md,
)


def test_development_prompt_starts_with_duplicate_preflight_before_changes():
    task = SimpleNamespace(title="Desenvolver menu", prompt="Adicione o menu solicitado.")
    prompt = development_prompt(task)
    assert "DUPLICATION PREFLIGHT" in DEVELOPMENT_DUPLICATE_GUARD
    assert "Do not create a parallel or second implementation" in prompt
    assert "If the feature already exists completely" in prompt
    assert prompt.index("DUPLICATION PREFLIGHT") < prompt.index("Only after completing that preflight")


def test_generated_agents_md_preserves_existing_rules_and_replaces_old_analysis():
    project = SimpleNamespace(
        name="Projeto teste",
        repository_url="https://github.com/a-castilho/projeto-teste.git",
        default_branch="main",
        agents_md="",
    )
    task = SimpleNamespace(id="12345678-abcd", title="Análise técnica")

    existing = (
        "# Regras existentes\n\n"
        "<!-- DEVPILOT-GENERATED-ANALYSIS:START -->\n"
        "relatório antigo\n"
        "<!-- DEVPILOT-GENERATED-ANALYSIS:END -->\n"
    )
    content = build_generated_agents_md(
        project,
        task,
        "Authorization: Bearer secret-token\nNovo relatório",
        existing,
    )

    assert content.startswith("# Regras existentes")
    assert "relatório antigo" not in content
    assert "Novo relatório" in content
    assert "secret-token" not in content
    assert "[REDACTED]" in content


def test_write_generated_agents_md_persists_only_the_instruction_file(tmp_path):
    project = SimpleNamespace(
        name="Projeto teste",
        repository_url="https://github.com/a-castilho/projeto-teste.git",
        default_branch="main",
        agents_md="",
    )
    task = SimpleNamespace(id="87654321-abcd", title="Análise técnica")

    content = write_generated_agents_md(Path(tmp_path), project, task, "Relatório concluído")

    target = Path(tmp_path) / "AGENTS.md"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == content
    assert project.agents_md == content
