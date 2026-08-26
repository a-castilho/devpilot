# Orquestrador de recuperação de CI/CD

## Objetivo

Fechar o ciclo entre uma falha real do GitHub Actions e a esteira de tarefas já existente no DevPilot, sem duplicar worker, executor, autocorreção, Git, PR, merge ou quality gates.

O orquestrador não substitui o CI e não considera uma alteração correta por conta própria. O GitHub Actions continua sendo a fonte oficial de validação. A responsabilidade desta camada é transformar uma falha acionável de CI em uma `Task` automática e segura para o worker existente.

## Estado auditado antes da implementação

A base atual já possui:

- workflow `CI` com os jobs `DevPilot policy`, `DevPilot full quality` e `DevPilot runtime image`;
- execução oficial de `bash scripts/test-all.sh`;
- artifacts de diagnóstico em `.artifacts/test-results`;
- Playwright/Chromium obrigatório no CI para o ciclo real do Modo Jogo;
- fila persistente de `Task` e `Run`;
- worker que consome tarefas em estado `queued`;
- `AutoRecoveryService` com tentativas limitadas para falhas operacionais seguras;
- fluxo análise → implementação → verificação → correção;
- executor e automação Git já existentes.

Portanto, essas capacidades não foram reimplementadas.

## Arquitetura implementada

```text
GitHub Actions
    |
    | workflow_run: completed + failure/timed_out
    v
POST /api/integrations/github/webhook
    |
    | HMAC SHA-256 obrigatório
    v
CI Failure Orchestrator
    |
    +--> identifica projeto gerenciado
    +--> gera fingerprint do evento
    +--> deduplica redelivery
    +--> aplica circuit breaker por branch
    +--> registra auditoria
    v
Task(source=ci-recovery, priority=100, approval=false)
    |
    v
Worker existente
    |
    +--> diagnóstico/correção
    +--> testes focados
    +--> bash scripts/test-all.sh
    +--> commit/push pela automação existente
    v
GitHub Actions revalida
    |
    +--> vermelho: novo evento, sujeito a dedupe/breaker
    +--> verde: gates existentes seguem o fluxo normal de PR/merge/deploy
```

## Receiver do GitHub

Endpoint:

```text
POST /api/integrations/github/webhook
```

O endpoint é separado das rotas autenticadas por sessão do usuário porque chamadas do GitHub não possuem token de sessão DevPilot. Isso não significa endpoint aberto: toda entrega precisa conter uma assinatura válida `X-Hub-Signature-256`, calculada com o segredo configurado em `DEVPILOT_GITHUB_WEBHOOK_SECRET`.

Sem segredo configurado o endpoint retorna `503`. Assinatura inválida retorna `401`.

Somente o evento `workflow_run` é processado. Dentro dele, somente `action=completed` com `conclusion=failure` ou `conclusion=timed_out` gera recuperação. Sucesso, cancelamento e eventos intermediários são ignorados.

## Idempotência

Cada falha recebe um fingerprint determinístico composto por:

- repositório;
- workflow;
- `run_id`;
- `run_attempt`;
- `head_sha`;
- conclusão.

O fingerprint é gravado como marcador interno no prompt da task. Se o GitHub reenviar a mesma entrega, o orquestrador retorna `duplicate` e não abre outra task.

Uma nova tentativa do mesmo workflow (`run_attempt` diferente) é uma ocorrência nova e pode gerar uma nova correção, respeitando o circuit breaker.

## Circuit breaker

Para impedir loops de `CI falha → corrige → CI falha → corrige` sem limite, o orquestrador permite no máximo **3 tasks de recuperação para a mesma branch dentro de 6 horas**.

Ao atingir o limite:

- nenhuma nova task automática é criada;
- um evento de auditoria `ci.recovery.circuit_open` é registrado;
- o estado retornado pelo receiver é `blocked`;
- o CI permanece vermelho e precisa de diagnóstico humano ou de uma nova janela de recuperação.

O worker mantém, separadamente, seu próprio limite de autocorreção operacional. Os dois mecanismos resolvem problemas diferentes e não devem ser fundidos.

## Regras da task automática

A task criada pelo CI possui:

- `source=ci-recovery`;
- prioridade `100`;
- `requires_approval=false`;
- vínculo ao workspace, usuário proprietário e projeto encontrados no cadastro existente;
- modo explícito `[DEVPILOT_MODE=fix]`;
- referência ao repositório, workflow, branch, SHA e run do GitHub.

O prompt estabelece regras de segurança:

1. localizar causa raiz;
2. corrigir somente o necessário;
3. não desativar, ignorar ou enfraquecer testes/gates para obter verde;
4. executar testes focados durante o diagnóstico;
5. executar `bash scripts/test-all.sh` antes de concluir;
6. deixar o GitHub Actions decidir o gate final.

## Configuração

No ambiente do DevPilot:

```bash
DEVPILOT_GITHUB_WEBHOOK_SECRET=<segredo-aleatorio-forte>
```

No GitHub, configurar um webhook do repositório ou da organização com:

```text
Payload URL: https://<host-devpilot>/api/integrations/github/webhook
Content type: application/json
Secret: o mesmo valor de DEVPILOT_GITHUB_WEBHOOK_SECRET
Event: Workflow runs
```

O segredo não deve ser colocado no frontend, commitado no repositório nem incluído em logs.

## Relação com erros de frontend

O orquestrador só consegue reagir automaticamente a uma regressão que algum gate consiga detectar. Para o travamento recente do Modo Jogo, essa condição já está atendida pelo gate Playwright/Chromium adicionado ao `DevPilot full quality` em 26 de agosto de 2026.

Assim, o fluxo esperado para regressões cobertas é:

```text
regressão de front
→ browser E2E falha
→ DevPilot full quality fica vermelho
→ webhook workflow_run chega ao DevPilot
→ task ci-recovery é criada
→ worker corrige e valida
→ push dispara nova execução do CI
→ somente CI verde permite seguir os gates posteriores
```

Uma regressão não coberta por teste continuará podendo escapar. Por isso, toda falha de produção corrigida deve ganhar um teste de regressão permanente quando tecnicamente possível.

## Observabilidade e auditoria

O orquestrador registra pelo serviço de auditoria existente:

- `ci.recovery.queued` quando cria uma recuperação;
- `ci.recovery.circuit_open` quando bloqueia um loop.

Os detalhes incluem repositório, workflow, run, tentativa, SHA, branch e fingerprint, sem armazenar o segredo do webhook.

## Critério de conclusão

A funcionalidade só deve ser considerada concluída quando:

- os testes unitários do parser e da assinatura HMAC passarem;
- o conjunto `bash scripts/test-all.sh` passar;
- o job `DevPilot full quality` do PR ficar verde;
- um evento real de `workflow_run` assinado puder criar exatamente uma task `ci-recovery` para um projeto gerenciado;
- redelivery do mesmo evento não duplicar a task;
- repetição acima do limite abrir o circuit breaker.

O merge e o deploy continuam subordinados aos gates já existentes do DevPilot.
