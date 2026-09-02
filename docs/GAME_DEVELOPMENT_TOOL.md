# Modo Jogo como ferramenta de desenvolvimento

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
