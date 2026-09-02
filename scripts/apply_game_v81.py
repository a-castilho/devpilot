from __future__ import annotations

from pathlib import Path
import subprocess

SOURCE_REF = "origin/feat/game-development-continuity-v80"

COPY_FILES = [
    "app/frontend_ui_routes.py",
    "app/services/failure_recovery.py",
    "app/static/build-game-url-bonus.js",
    "app/static/game/delivery-gate.js",
    "app/static/game/development-continuity.js",
    "app/static/game/final-delivery-summary.js",
    "app/static/game/game-bootstrap.js",
    "app/static/game/index.html",
    "app/static/game/runtime.js",
    "app/static/game/task-payload-guard.js",
    "app/static/product-delivery-ui.js",
    "tests/test_game_browser_e2e.py",
    "tests/test_game_development_continuity_v80.py",
    "tests/test_game_ships_stable_runtime_contract.py",
]


def copy_from_source(path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = subprocess.check_output(["git", "show", f"{SOURCE_REF}:{path}"])
    target.write_bytes(data)


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Padrão não encontrado em {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


for file_path in COPY_FILES:
    copy_from_source(file_path)

replace_once(
    "app/static/build-game.js",
    "evidence: 'Plano persistido, baseline executado e critérios de aceite ligados ao pedido.',",
    "evidence: 'Preflight de duplicidade concluído, System Design registrado ou dispensado com justificativa, baseline executado e critérios de aceite ligados ao pedido.',",
)

replace_once(
    "app/static/build-game.js",
    "mission: `Leia AGENTS.md, documentação e repositório antes de agir. Preserve literalmente o objetivo informado pelo usuário. Registre .devpilot/build-game.md com objetivo, estado inicial, escopo, fora de escopo, critérios de aceite, riscos, arquivos prováveis e comandos reais de instalação, execução, lint, build e testes. Execute a verificação de baseline. Não implemente a funcionalidade nesta etapa e não invente resultado.`",
    "mission: `Leia AGENTS.md, docs/SYSTEM_DESIGN.md, documentação aplicável e o repositório antes de agir. Preserve literalmente o objetivo informado pelo usuário. Antes de qualquer edição, faça o preflight de duplicidade: procure tarefas, execuções e alterações existentes que já atendam ou estejam atendendo o mesmo objetivo; quando existir trabalho válido, continue/reutilize em vez de criar implementação paralela. Classifique a mudança conforme docs/SYSTEM_DESIGN.md. Para SIMPLE, registre \"System Design dispensado\" com justificativa. Para STRUCTURAL, registre System Design conciso cobrindo arquitetura afetada, componentes, contratos, dados, segurança, dependências, falhas e recuperação, escalabilidade, observabilidade, deploy, compatibilidade, rollback, testes, riscos e trade-offs. Registre .devpilot/build-game.md com objetivo, estado inicial, resultado do preflight, decisão de System Design, escopo, fora de escopo, critérios de aceite, riscos, arquivos prováveis e comandos reais de instalação, execução, lint, build e testes. Execute a verificação de baseline. Não implemente a funcionalidade nesta etapa e não invente resultado.`",
)

replace_once(
    "app/static/game/delivery-gate.js",
    "- Leia AGENTS.md, documentação e .devpilot/build-game.md.\\n- Compare o OBJETIVO com critérios de aceite concretos.",
    "- Leia AGENTS.md, docs/SYSTEM_DESIGN.md, documentação e .devpilot/build-game.md.\\n- Na fase 1, confirme evidência do preflight de duplicidade e do System Design (ou da dispensa justificada para mudança SIMPLE) antes de aprovar.\\n- Compare o OBJETIVO com critérios de aceite concretos.",
)

DOC = """# Modo Jogo como ferramenta de desenvolvimento

O Modo Jogo é uma interface operacional sobre a esteira real do DevPilot. Ele não é uma simulação e não mantém uma esteira paralela.

## Fluxo canônico

Projeto → objetivo da entrega → Planejamento → Implementação → Execução → Testes → Documentação → Git → Entrega e revisão.

Cada fase possui uma tarefa de execução e um gate independente. `status=completed` da tarefa base não libera a próxima fase sozinho. O gate precisa provar a entrega com evidência real, conforme `docs/releases/v1.1.1.md`.

## Planejamento obrigatório

Antes de editar o projeto, a fase Planejamento deve:

1. ler `AGENTS.md`, documentação e o repositório;
2. executar preflight de duplicidade e continuar trabalho válido já existente em vez de criar implementação paralela;
3. classificar a mudança segundo `docs/SYSTEM_DESIGN.md`;
4. registrar dispensa justificada para mudança SIMPLE ou System Design conciso para mudança STRUCTURAL;
5. registrar objetivo, baseline, escopo e critérios de aceite em `.devpilot/build-game.md`.

## Continuidade por projeto

A seleção do projeto é parte do estado da rodada. Ao trocar de projeto, o jogo recupera a rodada daquele projeto. Ao retornar, continua da fase real já existente. `Nova rodada` é uma intenção explícita e não deve ressuscitar automaticamente a rodada anterior.

A listagem do jogo pagina projetos para funcionar em ambientes com muitos projetos sem transformar a tela em um carregamento pesado.

## Falhas e autocorreção

Falhas `failed` ou `blocked` entram no fluxo de recuperação. A recuperação deve usar a falha anterior como evidência, encontrar a causa raiz, não repetir cegamente a mesma ação e retestar a execução original. Só pede orientação humana quando a informação ou autorização não puder ser obtida pelo sistema.

## Entrega final

A vitória depende do tipo de projeto. Projetos web exigem entrega web verificável quando aplicável; APIs e serviços podem concluir com serviço verificável; CLI, automação e código podem concluir tecnicamente sem inventar uma URL pública. Em todos os casos a entrega deve ser rastreável por evidências, testes e Git.

## Carregamento e baixo consumo

O jogo é módulo opcional e só deve carregar após intenção explícita do usuário, conforme `docs/ENGINEERING_STANDARD.md`. O runtime não deve introduzir `MutationObserver` global, loaders ocultos ou uma segunda onda automática pós-login.

## Critério de pronto

A mudança do jogo só está pronta com sintaxe JavaScript, testes focados, contratos de continuidade, E2E de navegador e gates oficiais verdes. Regressões de tela preta, duplicação de execução, troca de projeto e retomada de rodada devem permanecer cobertas por testes.
"""
Path("docs/GAME_DEVELOPMENT_TOOL.md").write_text(DOC, encoding="utf-8")

TEST = """from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_planning_requires_duplicate_preflight_and_system_design():
    source = read("app/static/build-game.js")
    assert "preflight de duplicidade" in source
    assert "docs/SYSTEM_DESIGN.md" in source
    assert "System Design dispensado" in source
    assert "continue/reutilize" in source


def test_phase_one_gate_requires_planning_governance_evidence():
    source = read("app/static/game/delivery-gate.js")
    assert "preflight de duplicidade" in source
    assert "System Design" in source
    assert "fase 1" in source


def test_game_development_tool_documentation_exists():
    doc = read("docs/GAME_DEVELOPMENT_TOOL.md")
    for value in (
        "Continuidade por projeto",
        "Falhas e autocorreção",
        "Entrega final",
        "Carregamento e baixo consumo",
    ):
        assert value in doc
"""
Path("tests/test_game_development_tool_v81.py").write_text(TEST, encoding="utf-8")

print("GAME_V81_APPLIED=OK")
