# Worker lease e fencing

O runtime do orquestrador usa `task_orchestrator_runtime` para garantir que uma tarefa em execução tenha um único dono lógico por vez.

## Invariantes

- Cada claim recebe um `claim_owner` único, usado como fencing token. O PID do worker continua identificando o ator de auditoria, mas não é suficiente para provar posse porque pode ser reutilizado após restart.
- Um lease só pode ser renovado enquanto ainda não expirou e enquanto `task_id`, estado e `claim_owner` continuam pertencendo ao mesmo claim.
- O executor renova o lease durante o polling cooperativo. Se a posse mudar ou o lease expirar, o worker antigo falha fechado e não pode concluir a tarefa.
- `mark_worker_finished` e `mark_worker_controlled` verificam o fencing token antes de alterar estado final, aprendizado ou recompensa.
- A recuperação de lease vencido é compare-and-set: o `UPDATE` repete as condições observadas (`running`, owner e lease vencido). Uma renovação concorrente impede a recuperação antiga de sobrescrever o novo lease.

## Recuperação

Um lease expirado em estado `running` pode ser devolvido à fila. O worker que ainda estiver executando com o token antigo será impedido de finalizar quando observar a perda da posse.

Pedidos cooperativos de `pause_requested` e `cancel_requested` preservam a posse do worker ativo até que ele confirme a parada e converta o estado para `paused` ou `canceled`.

## Limites

O fencing protege as mutações persistidas do DevPilot. Ele não desfaz efeitos externos que um processo já tenha produzido antes de detectar a perda do lease. Por isso o executor também encerra o process group ativo assim que identifica `LostTaskClaim` durante o polling.
