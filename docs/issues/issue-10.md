# Issue #10 — Nova Tarefa: modal AgentOS com modo de análise somente leitura

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Fechada
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-20T02:12:04Z
- **Atualizada em:** 2026-08-20T02:22:09Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/10

## Planejado / descrição da issue

## Objetivo
Implementar no DevPilot o modal de Nova Tarefa conforme a referência visual enviada, com foco em contexto em linguagem natural e modo explícito de análise/diagnóstico.

## Escopo
- novo cabeçalho "O que você quer que a IA faça?";
- projeto, modo e título organizados no topo;
- textarea ampla de contexto;
- bloco "Análise assistida pelo AgentOS";
- prioridade e exigência de aprovação;
- scroll interno responsivo, sem overflow horizontal;
- modo "Analisar / diagnosticar" marcado de forma determinística;
- execução de análise isolada para não persistir alterações no repositório principal;
- manter compatibilidade com tarefas de desenvolvimento existentes;
- documentação e testes.

## Rollback
`backup/pre-task-modal-agentos-20260819`

## Compromisso geral
Sempre na melhor prática. No caminho do bem maior. Ir até o fim sem sair do caminho, seja ele qual for.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
