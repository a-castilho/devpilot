# DevPilot Repair Pipeline

## Objetivo

O Repair Pipeline transforma uma falha de execução em um fluxo autônomo, auditável e orientado por evidência. O objetivo é reduzir intervenção manual, evitar repetição de contexto para IA e impedir que a esteira avance com um “sucesso textual” sem prova técnica.

A regra central é:

> **process success + contract success + evidence success = task success**

Um `exit_code = 0` isolado não é suficiente quando a tarefa possui contrato de evidência.

## Fluxo

1. **Detecção** — o worker executa a tarefa e aplica os guards de execução.
2. **Evidence Gate** — tarefas Build Game/Jogo/Delivery Verifier exigem `.devpilot/build-game.md` não vazio.
3. **Self-healing** — falhas conhecidas passam pelo ciclo curto de autocorreção existente.
4. **Incident** — quando a autocorreção não resolve, o DevPilot cria um snapshot compacto com task, run, projeto, categoria, código e mensagem sanitizada.
5. **Repair Run** — a recuperação existente recebe `[DEVPILOT_REPAIR_PIPELINE_V1]` e executa diagnóstico de causa raiz, testes focados e verificações de integração.
6. **Delivery** — se houver mudança de código, o DevPilot cria commit na branch da recuperação, faz push e abre Pull Request com GitHub CLI.
7. **CI Gate** — o PR é acompanhado por `gh pr checks --watch --fail-fast`. CI com falha bloqueia o reteste da tarefa original.
8. **Reteste** — somente com entrega válida (`ready_to_retest`) ou correção ambiental sem diff (`no_changes`) a tarefa original volta para a fila.
9. **Prova final** — a tarefa original é executada novamente; seu resultado é a evidência final de que a causa raiz foi removida.

## Limite de autonomia

O Repair Pipeline **não faz merge automático**. Ele pode preparar commit, push, PR e acompanhar CI, mas o merge permanece fora da fronteira autônoma. Isso evita que uma recuperação técnica publique alterações irreversíveis sem a política de entrega apropriada.

## Incidente persistente

O prompt da tarefa de recuperação recebe um bloco como:

```text
[DEVPILOT_REPAIR_PIPELINE_V1]
[repair-incident:{...}]
```

O JSON contém somente contexto compacto e minimizado. Logs brutos continuam no `Run` e seguem as regras existentes de sanitização e autorização.

## Evidence Gate

`app/services/execution_guards.py` adiciona três garantias:

- tarefas de desenvolvimento usam `codex exec --sandbox workspace-write`;
- análises read-only não recebem permissão de escrita;
- tarefas `[Jogo]`, Build Game e Delivery Verifier só retornam sucesso quando `.devpilot/build-game.md` existe e não está vazio.

Também combina stdout com stderr em falhas quando o stderr contém apenas a mensagem benigna do Codex (`Reading additional input from stdin...`), evitando que o diagnóstico real seja ocultado.

## Entrega automática

`app/services/repair_pipeline.py` materializa uma recuperação bem-sucedida:

- `git status --porcelain` identifica se houve alteração;
- `git add -A` e `git commit` materializam a mudança;
- `git push -u origin <branch>` publica a branch;
- `gh pr create` abre o PR;
- `gh pr checks --watch --fail-fast` acompanha CI;
- `Run.commit_sha` e `Run.pull_request_url` recebem as evidências de entrega.

Se não houver diff, o fluxo assume uma possível correção ambiental e devolve `no_changes`; nesse caso, o reteste da tarefa original é obrigatório.

## Estados de entrega

| Estado | Significado | Retesta original? |
|---|---|---|
| `no_changes` | Correção ambiental ou sem diff | Sim |
| `ready_to_retest` | Commit/PR criado e CI aprovado ou não configurado | Sim |
| `ci_failed` | PR criado, CI falhou | Não |
| `delivery_failed` | Falha em commit, push, PR ou infraestrutura de entrega | Não |

## Economia esperada

A economia vem principalmente de evitar reanálises e prompts repetidos. O incidente persistente concentra os identificadores e a falha relevante; a tarefa de recuperação recebe o objetivo original e o contexto de erro sem depender de reconstrução manual da conversa.

O pipeline também executa validações focadas antes de depender do CI completo, reduzindo tempo de CPU e chamadas desnecessárias ao agente.

## Segurança e rollback

- credenciais não são copiadas para o incident snapshot;
- não há merge automático;
- falha de CI não libera a tarefa original;
- falha de entrega converte a recuperação em falha auditável;
- runs, commits e PRs permanecem como evidência histórica;
- a tarefa original só é retomada depois do gate de recuperação.

## Dependências operacionais

Para entrega por GitHub, o host do worker precisa ter:

- `git` funcional;
- `gh` instalado e autenticado ou ambiente equivalente;
- permissão de push para a branch de recuperação;
- acesso para criar Pull Requests e consultar checks.

Correções que dependam de credencial, permissão ou decisão humana continuam respeitando o gate de autorização existente no Failure Recovery.

## Testes

Os testes devem cobrir pelo menos:

- snapshot de incidente sem dados extras;
- reparo sem diff (`no_changes`);
- criação de commit, push e PR;
- CI aprovado;
- CI com falha bloqueando reteste;
- Evidence Gate Build Game;
- preservação do modo read-only;
- stdout real não mascarado por stderr benigno.
