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
5. **Baseline do workspace** — ao criar a tarefa de recuperação, o DevPilot registra quais caminhos já estavam sujos antes do reparo.
6. **Repair Run** — a recuperação recebe `[DEVPILOT_REPAIR_PIPELINE_V1]` e executa diagnóstico de causa raiz, testes focados e verificações de integração.
7. **Scoped Delivery** — somente caminhos que ficaram sujos depois do baseline podem ser staged automaticamente; alterações preexistentes permanecem intocadas.
8. **Delivery** — se houver mudança nova de código, o DevPilot cria commit na branch da recuperação, faz push e abre Pull Request com GitHub CLI.
9. **CI Gate** — o PR é acompanhado por `gh pr checks --watch --fail-fast`. CI com falha bloqueia o reteste da tarefa original.
10. **Reteste** — somente com entrega válida (`ready_to_retest`) ou correção ambiental sem diff novo (`no_changes`) a tarefa original volta para a fila.
11. **Prova final** — a tarefa original é executada novamente; seu resultado é a evidência final de que a causa raiz foi removida.

## Limite de autonomia

O Repair Pipeline **não faz merge automático**. Ele pode preparar commit, push, PR e acompanhar CI, mas o merge permanece fora da fronteira autônoma. Isso evita que uma recuperação técnica publique alterações irreversíveis sem a política de entrega apropriada.

## Incidente persistente

O prompt da tarefa de recuperação recebe um bloco como:

```text
[DEVPILOT_REPAIR_PIPELINE_V1]
[repair-incident:{...}]
[repair-baseline:{...}]
```

O incidente contém somente contexto compacto e minimizado. O baseline contém apenas a lista de caminhos que já estavam modificados ou não rastreados antes da recuperação. Logs brutos continuam no `Run` e seguem as regras existentes de sanitização e autorização.

## Evidence Gate

`app/services/execution_guards.py` adiciona três garantias:

- tarefas de desenvolvimento usam `codex exec --sandbox workspace-write`;
- análises read-only não recebem permissão de escrita;
- tarefas `[Jogo]`, Build Game e Delivery Verifier só retornam sucesso quando `.devpilot/build-game.md` existe e não está vazio.

Também combina stdout com stderr em falhas quando o stderr contém apenas a mensagem benigna do Codex (`Reading additional input from stdin...`), evitando que o diagnóstico real seja ocultado.

## Entrega automática com escopo controlado

`app/services/repair_pipeline.py` materializa uma recuperação bem-sucedida sem varrer sujeira anterior do repositório:

- `git status --porcelain=v1 -z --untracked-files=all` captura o baseline ao criar a recuperação;
- no final, o mesmo status é comparado com o baseline;
- somente caminhos novos (`estado atual - baseline`) entram no staging automático;
- `git add -A -- <paths>` limita o staging a esses caminhos;
- caminhos sensíveis como `.env`, chaves privadas e arquivos de credencial são bloqueados;
- `git diff --cached --name-only -z` confirma que nenhum caminho fora do escopo entrou no índice;
- `git commit` materializa a mudança;
- `git push -u origin <branch>` publica a branch;
- `gh pr create` abre o PR; se o PR já existir, `gh pr view` reaproveita a URL existente;
- `gh pr checks --watch --fail-fast` acompanha CI;
- `Run.commit_sha` e `Run.pull_request_url` recebem as evidências de entrega.

Se não houver diff novo em relação ao baseline, o fluxo devolve `no_changes`; nesse caso, o reteste da tarefa original é obrigatório. Se houver workspace sujo mas o baseline não estiver disponível, o pipeline falha fechado com `scope_unknown` e não faz staging automático.

## Estados de entrega

| Estado | Significado | Retesta original? |
|---|---|---|
| `no_changes` | Correção ambiental ou nenhum diff novo depois do baseline | Sim |
| `ready_to_retest` | Commit/PR criado e CI aprovado ou não configurado | Sim |
| `scope_unknown` | Workspace sujo sem baseline confiável | Não |
| `scope_blocked` | Caminho inseguro ou staging fora do escopo | Não |
| `ci_failed` | PR criado, CI falhou | Não |
| `delivery_failed` | Falha em commit, push, PR ou infraestrutura de entrega | Não |

## Economia esperada

A economia vem principalmente de evitar reanálises e prompts repetidos. O incidente persistente concentra os identificadores e a falha relevante; a tarefa de recuperação recebe o objetivo original e o contexto de erro sem depender de reconstrução manual da conversa.

O pipeline também orienta validações focadas antes do CI completo, reduzindo tempo de CPU e chamadas desnecessárias ao agente.

## Segurança e rollback

- credenciais não são copiadas para o incident snapshot;
- alterações que já existiam antes do reparo não entram no commit automático;
- arquivos de segredo conhecidos são bloqueados no staging automático;
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

Os testes cobrem:

- snapshot de incidente sem dados extras;
- round-trip do baseline;
- reparo sem diff (`no_changes`);
- fail-closed quando há sujeira sem baseline;
- preservação de caminhos preexistentes fora do staging;
- bloqueio de caminhos sensíveis;
- criação de commit, push e PR;
- reaproveitamento de PR existente em retry;
- CI aprovado;
- CI com falha bloqueando reteste;
- Evidence Gate Build Game;
- preservação do modo read-only;
- stdout real não mascarado por stderr benigno.
