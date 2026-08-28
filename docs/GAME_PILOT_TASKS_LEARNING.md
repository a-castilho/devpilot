# Painel do Piloto — tarefas, armamentos e aprendizagem

## Objetivo

O Modo Jogo é uma camada de apresentação isolada do DevPilot. O domínio de tarefas continua sendo a fonte de verdade; o jogo observa tarefas reais, traduz o estado operacional em linguagem de jogo e ensina o que está acontecendo sem alterar o executor.

## Regras arquiteturais

1. O Modo Jogo não executa trabalho diretamente. Toda execução nasce em `/api/tasks` e permanece vinculada ao projeto.
2. Tarefa real e armamento usam o mesmo `task_id`. Não existe uma segunda tarefa de jogo.
3. Fechar ou sair do jogo não cancela tarefas em execução.
4. Sair do jogo encerra a sessão do navegador: remove `devpilot-token`, limpa `sessionStorage` e navega para `/` com `location.replace`.
5. O runtime do jogo é um documento isolado em `/game/index.html`; dashboard e jogo não ficam montados ao mesmo tempo.
6. O painel educacional usa apenas dados já autorizados pelas APIs do usuário. Logs continuam sanitizados pelo backend.
7. Nenhum polling ou listener do jogo sobrevive à saída do documento.

## Painel do Piloto

O painel mostra, para o projeto selecionado:

- executando agora;
- aguardando/fila;
- concluídas;
- tarefas que precisam de atenção;
- armamento derivado do tipo de trabalho;
- estado operacional em linguagem simples;
- explicação `o que está acontecendo`;
- explicação `por que isso importa`;
- ação segura disponível.

### Estados

| Estado da tarefa | Estado no painel | Ação |
| --- | --- | --- |
| `queued`, `awaiting_approval` | Aguardando | Atualizar |
| `running`, `review` | Executando | Ver execução |
| `completed` | Concluída | Ver resultado |
| `failed`, `blocked` | Precisa de atenção | Ver erro / tentar novamente |
| `cancelled` | Cancelada | Ver resultado |

## Armamentos

O mapeamento é apenas visual e determinístico:

- teste/pytest/spec -> `Escudo de testes`;
- segurança/auth/permissão -> `Scanner de segurança`;
- deploy/vercel/render -> `Lançador de deploy`;
- bug/fix/correção/reparo -> `Canhão de reparo`;
- refactor/refatoração -> `Ferramenta de precisão`;
- diagnóstico/análise -> `Radar de diagnóstico`;
- demais tarefas -> `Ferramenta de construção`.

## Aprendizagem

A primeira versão é determinística e funciona sem IA. O painel explica a tarefa a partir do estado, título e prompt. Isso evita dependência de provedor para a experiência básica.

Camadas apresentadas ao usuário:

1. **Agora** — o estado atual da execução.
2. **Por quê** — a finalidade técnica daquele tipo de trabalho.
3. **Aprenda** — conceito curto relacionado ao armamento/tarefa.
4. **Resultado** — quando houver run disponível, o usuário pode abrir resumo/log sanitizado.

Uma evolução posterior pode acrescentar contextualização por IA e Event Store/SSE, sem mudar o contrato do painel.

## Atualização de estado

A implementação inicial faz atualização controlada a cada 15 segundos somente enquanto o documento está visível, além de atualizar após ações e mudanças de projeto/fase. O timer é cancelado em `pagehide`/`beforeunload`.

A evolução alvo é substituir esse mecanismo por eventos persistidos (`task_events`) e SSE com recuperação por sequência. Essa migração deve preservar o mesmo modelo visual e não criar dependência do executor em relação ao jogo.

## Ações

A primeira entrega habilita apenas ações que já possuem contrato seguro no backend:

- `Atualizar`;
- `Ver execução`/`Ver resultado` usando `/api/task-runs/{run_id}`;
- `Tentar novamente` para tarefas `failed` ou `blocked` usando `/api/tasks/{task_id}/retry`.

`Pausar`, `Retomar` e `Cancelar` só devem aparecer quando o worker possuir uma máquina de estados real e cooperativa para essas transições. A UI não deve simular um estado que o executor não respeita.

## Segurança e isolamento

- Token só é lido do `localStorage` para cabeçalho Bearer e nunca é exibido.
- O painel não lê credenciais, `.env` ou respostas brutas de provedores.
- O backend continua responsável por sanitizar logs.
- A consulta é limitada ao projeto selecionado e às APIs protegidas por autenticação.
- O logout do jogo não altera a fila nem mata workers.

## Critérios de aceite

- o jogo abre em documento separado do dashboard;
- o Painel do Piloto aparece no Modo Jogo sem carregar o `feature-loader.js`;
- tarefas reais do projeto aparecem com status e armamento;
- falha/bloqueio oferece retry, sem duplicar tarefa;
- detalhes usam run sanitizado existente;
- sair do jogo remove o token e retorna à tela inicial/login;
- tarefas continuam no backend após logout;
- nenhum `MutationObserver` novo é introduzido pelo painel;
- o painel funciona em desktop e mobile, uma coluna no viewport estreito.
