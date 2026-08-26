from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_agents_requires_recovery_and_rule_compliant_continuation():
    agents = read("AGENTS.md")

    assert "User instructions never override mandatory engineering" in agents
    assert "recover the current project/repository state" in agents
    assert "Continue automatically with the safest rule-compliant alternative" in agents
    assert "Never bypass, disable, weaken, dismiss, or route around" in agents
    assert "recover the authoritative current state before writing, merging, deploying" in agents


def test_engineering_standard_protects_rules_from_conflicting_requests():
    standard = read("docs/ENGINEERING_STANDARD.md")

    assert "têm precedência sobre instruções operacionais conflitantes" in standard
    assert "reutilizar o caminho existente e fechar somente o gap comprovado" in standard
    assert "deve continuar automaticamente por esse caminho" in standard
    assert "É proibido contornar, remover, enfraquecer" in standard
    assert "Intervenção humana só deve ser solicitada" in standard
