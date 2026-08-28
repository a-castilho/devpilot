# Acompanhamento de Workflow e Runners na Tela de Tarefas

## Objetivo

Transformar a tela de **Tarefas** no centro operacional do DevPilot, permitindo ao usuário acompanhar uma tarefa desde a análise até a validação e o deploy, sem precisar conhecer GitHub Actions, runners ou detalhes internos da infraestrutura.

A mesma infraestrutura deve oferecer ao **Super Admin** uma visão consolidada dos runners: disponibilidade, fila, execução atual, usuário/tarefa associada, duração, última atividade e falhas.

## Princípios

1. A tarefa é a âncora funcional. PR, commit, workflow, job, tentativa de reparo e deploy são execuções vinculadas a ela.
2. O frontend não consulta GitHub Actions diretamente. O backend consolida o estado externo e expõe uma API estável do DevPilot.
3. Eventos são idempotentes e tolerantes a duplicação, atraso e chegada fora de ordem.
4. Rerun ou Auto Repair cria nova tentativa de execução, não uma nova tarefa.
5. Estado de runner e estado de tarefa são relacionados, mas independentes. Um runner offline não pode transformar uma tarefa em falha de código.
6. O usuário comum recebe linguagem de produto; detalhes de infraestrutura ficam disponíveis progressivamente e para perfis autorizados.
7. Nenhum token, segredo, comando sensível ou log potencialmente secreto é enviado ao navegador.

## Experiência na tela de Tarefas

Cada cartão/linha de tarefa deve mostrar:

- estado funcional: aguardando, analisando, implementando, testando, aguardando runner, corrigindo, publicando, concluído ou falhou;
- progresso da execução atual;
- etapa atual e duração;
- PR e commit quando existirem;
- indicador do runner: aguardando, online/ocupado, executando esta tarefa, indisponível;
- última atualização;
- erro resumido e ação recomendada quando houver falha;
- acesso aos detalhes da execução sem expor log cru por padrão.

Ao expandir a tarefa, mostrar uma timeline semelhante a:

`Análise -> Implementação -> Pull Request -> Policy -> Full Quality -> Merge -> Runtime Image -> Deploy -> Health Check -> Concluído`

Etapas inexistentes para determinada tarefa devem ser omitidas ou marcadas como não aplicáveis.

### Estados visuais mínimos

- `queued`: aguardando capacidade/runner;
- `in_progress`: execução ativa;
- `success`: concluído com sucesso;
- `failure`: falha real da etapa;
- `cancelled`: cancelado;
- `skipped`: não aplicável ou condicionado;
- `timed_out`: excedeu o limite;
- `infra_error`: falha de infraestrutura, rede, runner ou provedor;
- `waiting_external`: aguardando GitHub, deploy ou outro provedor.

O DevPilot deve diferenciar explicitamente **falha de código** de **falha de infraestrutura**.

## Visão de Runner

### Usuário comum

Mostrar somente o necessário para compreender a própria execução:

- `Aguardando runner`;
- `Runner disponível`;
- `Executando sua tarefa`;
- tempo de espera;
- tempo em execução;
- posição aproximada na fila, somente quando calculável com segurança;
- indisponibilidade que esteja afetando a tarefa.

Não mostrar nomes, tarefas, projetos ou dados de outros usuários.

### Super Admin

Criar painel consolidado com:

- runner ID/nome lógico;
- status `online`, `busy`, `idle`, `offline`, `degraded`;
- labels/capacidades;
- heartbeat/última atividade;
- job/workflow atual;
- tarefa e projeto vinculados;
- usuário proprietário da execução;
- início e duração;
- quantidade de itens aguardando;
- taxa de sucesso/falha;
- falhas recentes de infraestrutura;
- versão do agente/runtime quando disponível;
- ações administrativas auditadas, quando suportadas futuramente.

A primeira versão deve ser somente observabilidade. Reiniciar, cancelar ou drenar runner exige autorização explícita, RBAC e auditoria e deve entrar em fase posterior.

## Modelo de dados proposto

### `TaskExecution`

Representa uma tentativa operacional vinculada à tarefa.

Campos essenciais:

- `id`;
- `task_id`;
- `attempt`;
- `status`;
- `current_stage`;
- `started_at`;
- `finished_at`;
- `last_event_at`;
- `failure_class`: `code`, `infra`, `external`, `unknown`;
- `failure_summary`;
- `created_at` / `updated_at`.

### `WorkflowRun`

- `id` interno;
- `task_execution_id`;
- `provider` (`github` inicialmente);
- `external_run_id` único por provider;
- `workflow_name`;
- `event`;
- `head_sha`;
- `head_branch`;
- `status`;
- `conclusion`;
- `run_attempt`;
- timestamps.

### `WorkflowJob`

- `workflow_run_id`;
- `external_job_id`;
- `name`;
- `status`;
- `conclusion`;
- `runner_id` quando conhecido;
- `started_at`;
- `finished_at`;
- `failure_summary` sanitizado.

### `Runner`

- `id`;
- `provider`;
- `external_runner_id`/nome lógico;
- `status`;
- `busy`;
- `labels`;
- `last_seen_at`;
- `current_job_id`;
- `runtime_version` opcional;
- `metadata` sanitizada.

### `Deployment`

- `task_execution_id`;
- `provider`;
- `environment`;
- `external_deployment_id`;
- `status`;
- `commit_sha`;
- `health_status`;
- timestamps.

### `ExecutionEvent`

Ledger imutável para auditoria e reconstrução:

- `event_id` idempotente;
- `source`;
- `event_type`;
- `task_execution_id` quando resolvido;
- `occurred_at`;
- `received_at`;
- payload mínimo/sanitizado ou hash/referência;
- resultado da aplicação do evento.

## Correlação tarefa -> Git -> workflow

A correlação deve usar identificadores persistidos, nunca inferência apenas por texto.

Ordem preferencial:

1. `task_id`/`execution_id` registrado quando o DevPilot cria branch/PR;
2. PR number e head SHA persistidos na execução;
3. workflow run correlacionado por PR/head SHA;
4. jobs vinculados pelo workflow run;
5. runner vinculado pelo job;
6. deploy correlacionado pelo commit SHA e ambiente.

Se a correlação não for determinística, registrar o evento como pendente e reconciliar posteriormente. Não atribuir execução a usuário/tarefa por heurística insegura.

## Coleta e sincronização

### GitHub

Preferir webhooks/eventos para baixa latência. Implementar também reconciliador periódico para recuperar eventos perdidos.

Eventos relevantes incluem mudanças de PR, workflow run/job, check/status e merge. O payload recebido deve ser validado e autenticado antes de persistência.

### Runner self-hosted

O estado operacional pode vir de duas fontes complementares:

1. metadados do provedor/GitHub quando disponíveis;
2. heartbeat do agente DevPilot no host, sem executar comandos arbitrários a partir da UI.

Heartbeat recomendado: 15-30 segundos enquanto online, contendo apenas identidade lógica, estado, versão e job atual. Considerar runner `degraded/offline` após janela configurável sem heartbeat.

### Reconciliação

Executar processo leve que:

- busca execuções não terminais;
- verifica runs/jobs cujo último evento ficou antigo;
- corrige divergências;
- fecha execuções órfãs somente após confirmação do provedor;
- classifica espera de runner separadamente de execução ativa.

## Máquina de estados

A máquina de estados deve impedir regressões inválidas causadas por eventos fora de ordem.

Exemplo:

`created -> queued -> in_progress -> success|failure|cancelled|timed_out`

Uma nova tentativa cria `attempt + 1`. Não alterar uma tentativa finalizada de `failure` para `success`; o sucesso pertence à tentativa posterior.

A projeção da tarefa apresenta o resultado mais recente e mantém o histórico das tentativas.

## API proposta

### Tarefa

- `GET /api/tasks/{task_id}/execution`
- `GET /api/tasks/{task_id}/executions`
- `GET /api/tasks/{task_id}/execution/events`

Resposta resumida deve incluir `status`, `stage`, `progress`, `runner`, `workflow`, `deployment`, `failure` e timestamps.

### Runners

- `GET /api/runners/me/summary` — visão limitada ao impacto nas execuções do usuário;
- `GET /api/admin/runners` — Super Admin;
- `GET /api/admin/runners/{runner_id}` — histórico/detalhes autorizados.

### Tempo real

Preferir SSE na primeira versão:

- `GET /api/tasks/{task_id}/execution/stream`;
- `GET /api/admin/runners/stream`.

SSE é suficiente para atualização servidor -> navegador, é simples operacionalmente e evita introduzir WebSocket sem necessidade bidirecional.

O frontend deve possuir fallback para polling com backoff caso a conexão SSE caia.

## Segurança e isolamento

- Validar assinatura de webhook.
- Aplicar RBAC em todas as consultas.
- Usuário só pode consultar tarefas, execuções e impacto de runner pertencentes ao seu escopo.
- Super Admin pode consultar visão global.
- Sanitizar logs e mensagens antes de persistir/exibir.
- Não persistir secrets recebidos em payloads.
- Não expor `GITHUB_TOKEN`, tokens de cloud, variáveis de ambiente ou comandos completos contendo credenciais.
- Toda futura ação administrativa em runner deve gerar auditoria com ator, alvo, motivo e resultado.

## Classificação de falhas

Criar classificador determinístico inicialmente baseado em origem/códigos conhecidos:

- `code`: teste, lint, policy, build determinístico da aplicação;
- `infra`: DNS, indisponibilidade de runner, disco, rede, timeout de provedor, daemon Docker;
- `external`: GitHub/Render/Vercel/PyPI indisponível ou rate limit;
- `unknown`: não classificado.

A classificação não deve converter automaticamente uma falha em sucesso. Ela serve para diagnóstico, UI, retry policy e Auto Repair.

Auto Repair deve atuar somente em classes permitidas. Falha puramente de infraestrutura deve preferir retry/reagendamento e não alteração de código.

## Métricas

Coletar pelo menos:

- tempo em fila;
- tempo de execução;
- duração total da tarefa;
- taxa de sucesso por workflow/job;
- retries por execução;
- falhas por classe;
- utilização do runner;
- tempo offline/degraded;
- tamanho da fila;
- tempo médio até início;
- tempo médio até recuperação.

Evitar cardinalidade alta em métricas com `user_id`, `task_id` ou SHA como labels de séries. Esses identificadores ficam em eventos/auditoria, não em labels globais de métricas.

## Interface recomendada

### Cartão da tarefa

Cabeçalho:

`Tarefa #123 | Testando | 04:32`

Corpo resumido:

`Policy OK -> Full Quality rodando -> Deploy aguardando`

Infra:

`Runner devpilot-ci-01 | ocupado nesta tarefa | 02:18`

Em falha:

`Infraestrutura: falha temporária de DNS ao acessar PyPI. Retry 2/4.`

Em espera:

`Aguardando runner disponível desde 17:31.`

### Super Admin

Bloco superior:

`Runners: 3 online | 2 ocupados | 1 idle | 0 offline | fila: 4`

Abaixo, tabela/lista com runner, tarefa, usuário, estágio, duração e saúde.

## Fases de implementação

### Fase 1 — Persistência e leitura

- modelos/migrações;
- correlação TaskExecution/PR/workflow;
- endpoints REST;
- projeção de status na tela de tarefas;
- testes unitários e integração.

### Fase 2 — Tempo real

- ingestão de eventos;
- SSE;
- fallback polling;
- idempotência e eventos fora de ordem;
- reconciliador.

### Fase 3 — Runner observability

- modelo Runner;
- heartbeat;
- fila e job atual;
- visão simplificada por usuário;
- painel Super Admin;
- métricas.

### Fase 4 — Auto Repair e deploy integrados

- tentativas explícitas;
- classificação de falhas;
- retry de infraestrutura;
- timeline de Auto Repair;
- deploy/health na mesma execução.

### Fase 5 — Controles administrativos

Somente após RBAC/auditoria maduros:

- cancelar job;
- drenar runner;
- reiniciar agente/runner quando tecnicamente suportado;
- reexecutar etapa autorizada.

## Critérios de aceite

1. Uma tarefa vinculada a PR mostra CI e jobs sem consulta manual ao GitHub.
2. `queued` é distinguido de `in_progress` e de falha.
3. Usuário identifica quando sua tarefa está aguardando runner.
4. Usuário não vê tarefas ou identidade de outros usuários através do runner.
5. Super Admin vê todos os runners e qual execução cada runner está processando.
6. Rerun mantém a mesma tarefa e cria nova tentativa.
7. Auto Repair aparece como tentativa/etapa auditável.
8. Eventos duplicados não duplicam runs/jobs.
9. Eventos fora de ordem não reabrem estados terminais incorretamente.
10. Falha de DNS/runner/provedor é apresentada como infraestrutura/external e não como erro de código.
11. Deploy e health check aparecem na timeline quando aplicáveis.
12. Nenhum segredo aparece em API, SSE, banco de eventos ou UI.
13. Testes de isolamento provam que usuário A não consulta execução/runner de usuário B.
14. A indisponibilidade do GitHub não derruba a tela de tarefas; a última projeção conhecida permanece visível com indicação de desatualização.

## Testes obrigatórios

- transições válidas e inválidas da máquina de estados;
- evento duplicado;
- evento atrasado/fora de ordem;
- rerun após failure;
- workflow cancelado;
- runner offline durante job;
- runner ocupado com tarefa de outro usuário;
- isolamento multiusuário;
- RBAC Super Admin;
- sanitização de segredo em mensagens/logs;
- reconciliação após perda de webhook;
- SSE reconnect e fallback polling;
- classificação code/infra/external;
- deploy success/failure e health check;
- compatibilidade com PR Auto Repair existente.

## Decisões arquiteturais

- **SSE antes de WebSocket:** fluxo principal é servidor -> cliente.
- **Ledger + projeção:** eventos preservam auditoria; projeção mantém leitura rápida.
- **Tentativas imutáveis:** retry não reescreve história.
- **Provider adapter:** GitHub é o primeiro provedor, não deve ficar acoplado ao domínio da tarefa.
- **Runner separado da tarefa:** infraestrutura possui ciclo de vida próprio.
- **Observabilidade antes de controle:** primeira entrega não deve permitir ações destrutivas sobre runners.

## Definition of Done

A funcionalidade está pronta quando um usuário consegue abrir Tarefas e responder, sem entrar no GitHub:

1. O que minha tarefa está fazendo agora?
2. Ela está esperando ou executando?
3. Qual etapa passou e qual falhou?
4. A falha é do meu código ou da infraestrutura?
5. O sistema está tentando novamente?
6. Foi mergeado/publicado?

E o Super Admin consegue responder:

1. Quantos runners estão online, ocupados, ociosos ou degradados?
2. O que cada runner está executando?
3. Para qual tarefa/projeto/usuário autorizado essa execução pertence?
4. Qual é a fila e há quanto tempo cada item espera?
5. Existe gargalo ou falha recorrente de infraestrutura?

A implementação deve preservar os gates existentes de CI, o isolamento multiusuário, o PR Auto Repair e a auditoria do DevPilot.