# Issue #13 — Codex: detectar limite, usar fallback isolado e permitir reexecução

> Documento gerado automaticamente a partir da issue. Edite a issue no GitHub; este arquivo será sincronizado novamente.

## Metadados

- **Status:** Fechada
- **Autor:** @acastilho
- **Responsáveis:** —
- **Labels:** —
- **Milestone:** —
- **Criada em:** 2026-08-20T04:03:09Z
- **Atualizada em:** 2026-08-20T04:14:28Z
- **Fonte:** https://github.com/a-castilho/devpilot/issues/13

## Planejado / descrição da issue

## Problema
Uma tarefa de desenvolvimento pode falhar com a mensagem do Codex `You've hit your usage limit`, mesmo quando o DevPilot possui conexões de IA cadastradas. Hoje o executor de escrita chama o Codex CLI usando a sessão local do ChatGPT e não classifica corretamente esse caso.

## Objetivo
Tornar a execução resiliente sem esconder custos nem criar loops automáticos.

## Solução
- classificar erros do Codex (`usage_limit`, `rate_limit`, `auth`, `transient`, `execution`);
- executar primeiro com a sessão normal do Codex/ChatGPT;
- quando houver limite/rate limit, tentar uma única vez o Codex com `CODEX_HOME` isolado e uma chave OpenAI ativa já armazenada no vault;
- nunca reutilizar o `auth.json` da sessão ChatGPT no fallback API;
- se não houver fallback disponível, marcar a tarefa como `blocked`, não `failed`;
- registrar provedor, modo de autenticação, tentativa e diagnóstico sanitizado no run;
- endpoint e botão para reexecutar tarefas `blocked`/`failed`;
- não fazer fallback para Ollama/Anthropic/Google em tarefas que escrevem repositório enquanto não existir executor agentivo de escrita seguro para esses provedores;
- testes e documentação.

## Segurança
A chave permanece no vault e será materializada somente em diretório temporário com permissão restrita durante o subprocesso Codex. Nenhum segredo deve aparecer em logs, argumentos ou frontend.

## Rollback
`backup/pre-codex-fallback-20260820`

## Regra de revisão

A PR deve referenciar esta issue e comparar **planejado x implementado x resultado observável/tela**. Mudanças visuais exigem evidência antes/depois; mudanças não visuais exigem evidência equivalente.
