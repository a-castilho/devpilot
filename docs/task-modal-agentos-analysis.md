# Modal de Nova Tarefa — AgentOS

## Objetivo

O modal de Nova Tarefa foi redesenhado para receber contexto em linguagem natural e deixar explícito o tipo de trabalho esperado da IA antes de registrar a tarefa.

## Experiência

A interface apresenta:

- projeto;
- modo da tarefa;
- título;
- contexto amplo para análise;
- orientação dinâmica do AgentOS;
- prioridade;
- exigência de aprovação;
- ação final coerente com o modo selecionado.

Os modos disponíveis são:

- **Analisar / diagnosticar**;
- **Desenvolver / implementar**;
- **Corrigir / depurar**;
- **Revisar / validar**.

## Modo de análise somente leitura

O frontend inclui o marcador interno `[DEVPILOT_MODE=analysis-read-only]` na instrução enviada ao backend. O marcador não altera o contrato público de criação de tarefas e mantém compatibilidade com tarefas existentes.

O executor reconhece esse marcador e também mantém compatibilidade com a análise técnica anterior que contém a instrução `Não modifique arquivos`.

Ao executar uma análise:

1. o repositório principal é atualizado apenas por operações normais de fetch;
2. uma worktree descartável é criada a partir de `origin/<branch-padrão>`;
3. o agente executa a análise nesse ambiente isolado;
4. qualquer alteração acidental fica restrita à worktree temporária;
5. o resultado registra se houve tentativa de alteração;
6. a worktree é removida e podada ao final;
7. nenhuma alteração analisada é persistida no branch de trabalho do projeto.

Esse isolamento corrige o comportamento anterior em que uma tarefa de análise seguia o mesmo executor destinado a implementação.

## Responsividade

O diálogo usa largura máxima de 760 px, altura limitada pela viewport e scroll vertical interno. Em telas pequenas, os grids de modo/título e prioridade/aprovação passam para uma coluna, evitando overflow horizontal.

## Arquivos principais

- `app/static/index.html`
- `app/static/task-modal.css`
- `app/static/task-modal.js`
- `app/services/executor.py`
- `tests/test_executor_read_only.py`

## Rollback

Versão anterior preservada em:

`backup/pre-task-modal-agentos-20260819`

## Compromisso geral

Sempre na melhor prática. No caminho do bem maior. Ir até o fim sem sair do caminho, seja ele qual for.
