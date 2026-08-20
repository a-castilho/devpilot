# Recuperação de execução do Codex

## Problema observado

Tarefas de desenvolvimento que modificam repositórios usam o Codex CLI. Quando esse CLI está autenticado pela sessão ChatGPT, a execução depende do limite disponível nessa sessão. Uma conexão de IA salva no DevPilot não substitui automaticamente essa autenticação do Codex.

O caso que motivou esta rotina retorna JSONL semelhante a `You've hit your usage limit`. Esse evento não significa que o código do projeto falhou; significa que o executor externo ficou sem capacidade para continuar.

## Comportamento implementado

Para tarefas de escrita, o DevPilot executa a seguinte sequência:

1. usa o Codex CLI com a sessão ChatGPT atual;
2. classifica falhas em `usage_limit`, `rate_limit`, `auth`, `transient` ou `execution`;
3. em `usage_limit` ou `rate_limit`, confirma que a worktree continua exatamente no mesmo estado;
4. se existir uma conexão OpenAI ativa e o fallback estiver habilitado, faz uma única tentativa com autenticação por API key;
5. essa tentativa usa um `CODEX_HOME` temporário e isolado, sem reutilizar `~/.codex/auth.json`;
6. o arquivo temporário `auth.json` recebe permissão `0600` e é removido quando o subprocesso termina;
7. a API key nunca é colocada nos argumentos do processo e nunca é devolvida nos logs ou no frontend;
8. se não houver capacidade alternativa, a tarefa fica `blocked` em vez de `failed` e pode ser reexecutada sem duplicar seu contexto.

## Proteção contra estado parcial

O fallback automático não é executado quando a primeira tentativa deixou alterações na worktree. Nesse cenário, o DevPilot retorna `partial_changes_detected` e bloqueia a tarefa para revisão humana.

Isso evita executar um segundo agente sobre alterações incompletas sem saber quais decisões já foram tomadas pela primeira tentativa.

## Fallback de API e custo

O fallback OpenAI API é independente do limite da sessão ChatGPT e pode consumir créditos da API configurada. Ele é habilitado por padrão, mas pode ser desligado globalmente:

```text
DEVPILOT_CODEX_API_FALLBACK_ENABLED=false
```

Também é possível reservar uma conexão OpenAI específica pelo nome cadastrado em **Modelos de IA**:

```text
DEVPILOT_CODEX_API_FALLBACK_CONNECTION_LABEL=Codex Fallback
```

O projeto pode sobrescrever esses valores em `codex_config` com `api_fallback` e `api_fallback_connection_label`.

## Por que não usar Anthropic, Gemini ou Ollama para escrever o repositório

O AgentOS já consegue conversar com OpenAI, Anthropic, Google e Ollama. Isso não torna automaticamente esses provedores equivalentes ao executor Codex de escrita.

Um fallback que modifica arquivos precisa preservar sandbox, comandos, diff, branch, testes, políticas e rastreabilidade. Enquanto não existir um executor agentivo de escrita com essas garantias para os demais provedores, eles permanecem disponíveis para análise/planejamento, mas não substituem automaticamente o Codex em tarefas que alteram o repositório.

## Interface

Tarefas bloqueadas mostram diagnóstico amigável em vez do JSONL bruto como mensagem principal. O relatório informa:

- executor;
- provedor utilizado;
- modo de autenticação;
- cadeia de tentativas;
- motivo do bloqueio;
- se o fallback de API foi usado e pode consumir créditos;
- próxima ação sugerida.

Tarefas `blocked` ou `failed` exibem **Reexecutar**. A reexecução recoloca a mesma tarefa na fila e preserva todos os runs anteriores para auditoria.

## Auditoria

Cada execução registra `failure_code`, `provider`, `auth_mode` e `fallback_used` na trilha de auditoria. A ação manual de reexecução registra `task.retry_requested` com o status anterior.

## Rollback

A versão anterior está preservada em:

`backup/pre-codex-fallback-20260820`

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**
