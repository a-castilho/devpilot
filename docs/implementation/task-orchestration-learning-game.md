# Implementação — Orquestração de tarefas, aprendizado e Modo Jogo

## Objetivo

Transformar o fluxo de trabalho hoje realizado em formato de ping-pong — analisar, implementar, avançar, corrigir, validar e concluir — em uma experiência nativa do DevPilot. O mesmo fluxo deve funcionar por botão, chat, voz ou avanço automático, sempre com a mesma política de autorização, auditoria e rastreabilidade.

A experiência não deve apenas executar trabalho. Cada etapa deve ensinar o usuário e, no Modo Jogo, converter a conclusão real de tarefas em progresso de missão e recompensa.

## Princípios obrigatórios

1. Existe uma única fonte de verdade para transição de tarefas. UI, chat, voz e automações não implementam regras próprias; todos chamam o mesmo orquestrador.
2. `Próximo` significa executar somente a próxima ação segura e determinística.
3. Ações críticas continuam parando em gates explícitos de autorização.
4. Parar uma tarefa não significa reverter efeitos já aplicados.
5. Excluir na interface deve ser arquivamento lógico, preservando runs e auditoria.
6. Conclusão deve ser baseada em evidência real, nunca em simulação de sucesso.
7. O aprendizado contextual é parte do ciclo de execução, não um recurso opcional separado.
8. No Modo Jogo, recompensa só ocorre quando a tarefa realmente alcança estado concluído válido.

## Hierarquia de missão

O produto deve diferenciar claramente três níveis:

- **Missão geral do projeto**: objetivo macro, por exemplo construir e colocar o projeto em funcionamento.
- **Missão de tarefa**: unidade concreta de trabalho dentro da missão geral.
- **Etapas da tarefa**: analisar, executar, verificar, corrigir quando necessário e concluir.

Concluir uma etapa não conclui a missão de tarefa. Concluir uma tarefa avança a missão geral. A recompensa do Modo Jogo deve ser associada à missão de tarefa concluída, sem duplicação de XP por retries ou reprocessamentos.

## Arquitetura proposta

### `TaskOrchestrator`

Responsável por:

- `next(task_id)`
- `pause(task_id)`
- `resume(task_id)`
- `cancel(task_id)`
- `archive(task_id)`
- `auto_advance(task_id)`
- determinar próxima etapa
- consultar política de autorização
- registrar auditoria
- garantir idempotência

O serviço deve reutilizar o fluxo existente em `task_flow.py`, `alternating_flow.py` e `worker.py`, evitando uma segunda máquina de estados concorrente.

### `TaskStateMachine`

Estados funcionais recomendados:

- `queued`
- `running`
- `pause_requested`
- `paused`
- `cancel_requested`
- `canceled`
- `blocked`
- `failed`
- `completed`
- `archived`

Toda transição precisa ser explícita e validada. Transições inválidas retornam conflito e não alteram estado.

### Claim e concorrência

Antes de habilitar múltiplos workers ou avanço concorrente, o claim da tarefa deve ser atômico. Requisitos:

- somente um worker pode possuir a tarefa;
- clique repetido em `Próximo` não pode duplicar execução;
- chamadas de chat e UI concorrentes devem produzir o mesmo resultado idempotente;
- lease/ownership deve permitir recuperação após worker morto;
- transições devem usar versionamento ou locking transacional.

## Experiência do usuário

### Painel Em andamento

Cada tarefa ativa deve apresentar:

- projeto;
- título da tarefa;
- missão geral relacionada;
- etapa atual;
- progresso visual;
- última ação executada;
- aprendizado da etapa;
- próxima ação prevista;
- indicação de risco/gate;
- botões contextuais.

Botões esperados:

- `Próximo`
- `Continuar automaticamente`
- `Parar`
- `Retomar`
- `Excluir`/arquivar
- ação crítica específica, como `Autorizar deploy`, quando aplicável

Não usar um botão genérico de aprovação quando for possível informar exatamente o que será autorizado.

## Aprendizado contextual

Cada etapa deve produzir um bloco pedagógico curto, preferencialmente em balões/context cards próximos à ação executada:

- **O que aconteceu**
- **Por que foi feito assim**
- **Conceito técnico envolvido**
- **O que observar no código/log/teste**
- **O que o usuário aprendeu nesta etapa**

O nível de detalhe deve acompanhar o perfil do usuário. O aprendizado precisa ser baseado em evidência real da execução.

## Conclusão da tarefa e documentação

Ao atingir `completed`, a interface deve exibir **Gerar documentação**.

A geração deve usar somente dados persistidos e auditáveis:

- título e contexto original;
- projeto;
- runs;
- summaries;
- evidências de executor;
- commit SHA, quando registrado;
- pull request, quando registrado;
- testes/validações registradas;
- status final;
- aprendizado e próximos passos.

A documentação inicial é Markdown e é gerada sob demanda pelo endpoint:

`POST /api/tasks/{task_id}/documentation`

Regras:

- somente tarefas `completed` podem gerar o documento;
- segredos conhecidos devem ser sanitizados;
- gerar documento não altera código do projeto;
- a geração deve criar evento de auditoria `task.documentation_generated`;
- adicionar o documento ao repositório é uma ação futura separada, sujeita à política de escrita/push.

### UI implementada nesta entrega

No painel de tarefas, tarefas concluídas passam a apresentar o botão **Gerar documentação**. O navegador gera um arquivo `.md` contendo o fechamento técnico da tarefa. A ação pode ser repetida e sempre reflete os dados persistidos naquele momento.

## Integração com Modo Jogo

Quando uma tarefa for concluída de forma válida:

1. marcar a missão de tarefa como concluída;
2. registrar evento de recompensa idempotente;
3. conceder XP/item/progresso apenas uma vez;
4. mostrar o aprendizado conquistado;
5. avançar a missão geral do projeto;
6. permitir abrir a documentação da implementação.

Retries, reloads e regeneração de documentação não podem conceder recompensa adicional.

## Fases de implementação

### Fase 1 — Fundação

- claim atômico;
- máquina de estados;
- idempotência;
- `TaskOrchestrator`;
- política de próxima ação.

### Fase 2 — Controles

- endpoints `next`, `pause`, `resume`, `archive`;
- painel Em andamento;
- integração com chat e voz;
- avanço automático até gate crítico.

### Fase 3 — Cancelamento real

- cancelamento cooperativo;
- processo/grupo de processo identificável;
- `cancel_requested` observado pelo worker/executor;
- recuperação segura de processos órfãos.

### Fase 4 — Aprendizado

- balões contextuais;
- registro de learning events;
- resumo por tarefa;
- histórico pedagógico do usuário.

### Fase 5 — Gamificação

- missão de tarefa;
- recompensa idempotente;
- integração com missão geral;
- XP/itens/progresso derivados de conclusão real.

## Critérios de aceite globais

- clicar `Próximo` e dizer `próximo` pelo chat produzem a mesma transição;
- dois comandos concorrentes não criam duas execuções;
- avanço automático para em fronteira crítica;
- `Parar` nunca promete interrupção imediata enquanto cancelamento real não estiver disponível;
- `Excluir` preserva evidência e auditoria;
- toda tarefa concluída pode gerar documentação técnica;
- documentação não inventa commits, testes ou PRs inexistentes;
- aprendizado é mostrado no fechamento de cada etapa;
- recompensa no Modo Jogo ocorre uma única vez por tarefa concluída;
- CI e testes de regressão cobrem backend, frontend e regras de idempotência.

## Estado desta entrega

Implementado nesta entrega:

- endpoint de documentação para tarefa concluída;
- geração de Markdown baseada em Task + Run;
- sanitização dos campos textuais e payloads de execução;
- evento de auditoria ao gerar documento;
- botão **Gerar documentação** no painel de tarefas concluídas;
- download do Markdown pelo navegador;
- testes de contrato do endpoint, conteúdo e integração do bundle.

Ainda pertencem às próximas entregas do orquestrador:

- `Próximo` centralizado;
- pausa/retomada formal;
- arquivamento lógico;
- claim atômico;
- cancelamento real;
- learning events persistidos;
- recompensa de missão de tarefa no Modo Jogo.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

