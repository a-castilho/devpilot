# Issue #73 — fix: corrigir função atualizar no bashrc local

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Fechada
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-24T13:20:54Z
- **Atualizada em:** 2026-08-29T18:52:25Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/73

## Planejado / descrição da issue

## Problema
Ao abrir um shell, o Bash reporta erro de sintaxe na linha com `atualizar() { atualizar-local "$@"; }`.

## Evidência local
A suíte completa do DevPilot no commit `301b2c6` passou com **211 testes aprovados**, portanto o problema não está no app, mas no bootstrap local do shell.

## Correção necessária
- garantir que o instalador de comandos use sintaxe válida e idempotente no `.bashrc`;
- remover/evitar definição conflitante de alias/função `atualizar`;
- validar com `bash -n ~/.bashrc`;
- preservar os comandos `atualizar-local`, `atualizar`, `reconstruir-sistema` e `reconstruir`.

## Critério de aceite
Novo shell abre sem erro de sintaxe e `type atualizar` resolve para a função/comando esperado.

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
