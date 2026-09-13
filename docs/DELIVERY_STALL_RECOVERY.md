# Recuperação automática de entrega parada

## Contexto

O fluxo de entrega final pode chegar a 100% das fases do projeto e, ainda assim, precisar de uma etapa adicional para materializar o produto no branch remoto e publicar uma URL real. Essa correção é representada por uma tarefa interna `delivery-recovery`.

Foi identificado um caso em homologação em que a missão permanecia indefinidamente em `repairing` enquanto a tarefa interna continuava em `queued`. A interface mostrava “Publicando e validando URL”, mas não existia avanço operacional. Também havia uma falha de ciclo de vida: depois de atingir o limite de retries de uma tarefa, o guard podia criar uma nova tarefa e reiniciar o contador, permitindo um loop sem limite global observável pelo usuário.

## Classificação

Mudança **ESTRUTURAL**.

Motivo: altera máquina de estados de entrega, recuperação automática, processamento assíncrono e observabilidade. Não é uma correção apenas visual.

## Objetivos

1. Uma missão em 100% nunca pode permanecer indefinidamente em `queued` sem diagnóstico.
2. O ser humano continua sendo o último recurso.
3. Recuperações devem ser idempotentes e limitadas.
4. A ausência de código publicável no branch remoto continua sendo um bloqueio real de entrega; não deve ser mascarada por uma URL antiga.
5. O DevPilot deve tentar retomar automaticamente a mesma correção antes de declarar falha.
6. Depois do limite seguro, o sistema deve exibir um estado terminal explícito em vez de simular progresso.

## Arquitetura

O mecanismo fica em `app/services/delivery_stall_recovery.py` e trabalha em conjunto com:

- `delivery_product_guard.py`: prova se o branch remoto contém uma aplicação publicável e cria a tarefa de reparo;
- `task_orchestrator.py`: reivindica tarefas da fila com lease e fencing;
- `embedded_worker.py`: executa tarefas em homologação quando não existe worker dedicado;
- `delivery_url_recovery.py`: reconcilia publicação e valida a URL pública real.

### Fluxo

```text
Projeto 100%
   |
   v
Product Guard
   |
   +-- branch remoto OK --------------------------+
   |                                               |
   |                                               v
   +-- branch incompleto -> delivery-recovery -> Worker
                                  |
                                  +-- executa -> prova remota -> deploy -> valida URL
                                  |
                                  +-- queued por > 120s
                                          |
                                          v
                                   Stall Recovery
                                          |
                         +----------------+----------------+
                         |                                 |
                      nudge 1/2                     tentativa falha
                         |                                 |
                         +----------> retry seguro <-------+
                                              |
                                      limite esgotado
                                              |
                                              v
                                       repair_exhausted
```

## Detecção de stall

Uma tarefa é considerada candidata quando:

- o projeto está com `delivery.status=repairing`;
- existe `repair_task_id` válido;
- a tarefa pertence ao mesmo workspace/projeto;
- `source=delivery-recovery`;
- status da tarefa é `queued`;
- `updated_at`/`created_at` está sem mudança por pelo menos 120 segundos.

Tarefas `running` não são interrompidas por este watchdog. Execuções em andamento continuam protegidas pelo lease/fencing do `TaskOrchestrator`.

## Recuperação

Para cada tentativa de reparo:

- até duas reativações são permitidas;
- prioridade é restaurada para 100;
- autorização humana não é exigida para esta autocorreção interna;
- o evento fica persistido no prompt e no audit log;
- a UI recebe metadados em `delivery.stall_recovery`.

Se o worker ainda não reivindicar a tarefa depois dessas reativações, a tentativa atual é marcada como `failed`. O `delivery_product_guard` então usa seu mecanismo existente de retry seguro e reavalia o branch remoto.

## Correção do loop infinito

Quando uma tarefa `delivery-recovery` chega a `failed` ou `blocked` e já consumiu `MAX_SAFE_RETRIES`, ela é preservada como a tarefa terminal esgotada. O sistema não cria uma nova tarefa zerando o contador.

Com isso, `_state_for_repair` consegue publicar corretamente:

- `status=blocked`;
- `delivery_gate=repair_exhausted`;
- mensagem de último recurso humano.

## Worker de homologação

Homologação precisa ter um executor efetivo. O serviço Docker do DevPilot contém Codex/Git e deve operar com:

- `DEVPILOT_EXECUTION_ENABLED=true`;
- `DEVPILOT_EMBEDDED_WORKER=true`.

O serviço Python que atende a API pode continuar sem executar Codex. Essa separação evita depender de uma sessão do navegador para avançar a fila.

## Observabilidade

Eventos adicionados:

- `project.delivery_repair_stall_requeued`;
- `project.delivery_repair_stall_failed`.

Logs de runtime:

- `[delivery-stall] requeued ...`;
- `[delivery-stall] failed stale attempt ...`;
- `[delivery-stall] recovered=...`.

O estado persistido também inclui `delivery.stall_recovery`, com status, número da reativação, instante e causa.

## Segurança e isolamento

- A recuperação só atua em tarefa cujo `workspace_id` e `project_id` correspondem ao projeto.
- Não altera credenciais.
- Não inventa URL pública.
- Não marca entrega como concluída sem a validação já existente do produto/URL.
- Não interrompe tarefa em execução.

## Rollback

O rollback é simples:

1. remover a chamada `start_delivery_stall_recovery()` de `app/services/__init__.py`;
2. remover `app/services/delivery_stall_recovery.py`;
3. desabilitar `DEVPILOT_EMBEDDED_WORKER` no serviço executor, se necessário.

Nenhuma migração de banco é necessária.

## Critérios de aceite

- tarefa de reparo `queued` por mais de 120 s é reativada automaticamente;
- a recuperação é limitada e auditável;
- uma tentativa que não é reivindicada deixa de aparecer eternamente como progresso;
- retries esgotados não geram uma nova tarefa com contador zerado;
- missão só termina com prova remota e URL pública válida;
- homologação possui worker capaz de consumir a fila;
- nenhum fluxo exige ação humana antes de esgotar as tentativas automáticas.
