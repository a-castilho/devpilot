# DevPilot AgentOS — seu desenvolvedor e orquestrador de agentes

DevPilot é um SaaS leve para automatizar desenvolvimento de software por dashboard, API,
voz ou agentes. Ele organiza múltiplos projetos e tarefas, aplica instruções `AGENTS.md`,
controla configurações do Codex, executa trabalho em branches isoladas e registra cada
decisão em uma trilha de auditoria encadeada por hash.

O núcleo **AgentOS** adiciona catálogo de agentes, planejamento em grafo, execução persistente,
memória/RAG local, gateway para modelos generativos e embeddings via Ollama e uma interface
MCP para que outros hosts de IA consumam essas capacidades.

## O que o MVP entrega

- dashboard responsivo/PWA para desktop e celular;
- projetos com URL Git, branch, `AGENTS.md` e perfil Codex;
- tarefas vindas do dashboard, voz ou API;
- fila persistente e worker independente;
- aprovação humana para ações de risco;
- executor Codex com `subprocess` sem shell e timeout;
- vault criptografado para múltiplos provedores de IA;
- auditoria de comandos, configuração, aprovação e execução;
- política de hosts Git permitidos e isolamento de diretórios;
- Docker Compose com aplicação, worker e PostgreSQL;
- SQLite para desenvolvimento local sem infraestrutura adicional;
- AgentOS com agentes especialistas e grafo de dependências;
- executor real do grafo com Command, State Machine e Saga;
- idempotência por execução, retries com backoff e checkpoints persistentes;
- retomada explícita depois de falha/compensação;
- RAG local com chunking, embeddings e similaridade cosseno;
- gateway HTTP para LLM/embeddings sem carregar frameworks de ML no processo FastAPI;
- servidor MCP v2 com ferramentas de catálogo, planejamento e busca de conhecimento.

## Arquitetura

```text
PWA / API / voz / MCP
        │
        ▼
DevPilot FastAPI ── política ── auditoria hash-chain
        │
        ├── AgentOS
        │    ├── planner / specialists
        │    ├── graph executor + state machine
        │    ├── checkpoints / retries / saga
        │    ├── RAG / embeddings ── SQLite
        │    └── model gateway ── Ollama HTTP ── transformer model
        │
        ├── PostgreSQL/SQLite
        └── vault criptografado

worker
  ├── AgentOS graph tick
  └── DevPilot task ── projeto isolado ── Codex CLI ── Git branch
```

O plano do AgentOS é determinístico por padrão. Isso mantém o plano de controle disponível
mesmo quando nenhum modelo está carregado. Durante a execução, etapas de análise usam o
Language Model Port; etapas de implementação que precisam de `repo.write` são delegadas ao
executor existente do DevPilot e ficam em branch isolada, sem push/merge/deploy automático.

A arquitetura detalhada e as regras SOLID/Hexagonal/Clean estão em
`docs/agentos-architecture.md`.

## Perfil para Linux com 4 GB de RAM

Para desenvolvimento local de baixo consumo, prefira:

1. SQLite (`DEVPILOT_DATABASE_URL=sqlite:///./data/devpilot.db`);
2. API e worker em processos separados, iniciando o worker apenas quando precisar executar;
3. Ollama nativo no host, com um modelo de chat pequeno configurável;
4. `embeddinggemma` (ou outro modelo de embeddings disponível no seu Ollama) para RAG;
5. uma tarefa/agente executando por vez;
6. Docker/PostgreSQL apenas quando estiver validando o ambiente de produção.

O executor avança uma única transição/comando do grafo por tick do worker. Isso reduz picos de
RAM e torna cada etapa retomável. Se o serviço de embeddings estiver indisponível, o AgentOS
possui um embedding hashing de 256 dimensões como fallback operacional.

## Executar localmente

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8080
```

Em outro terminal, quando precisar executar o grafo e tarefas de desenvolvimento:

```bash
source .venv/bin/activate
python -m app.worker
```

Abra `http://localhost:8080` e use o valor de `DEVPILOT_BOOTSTRAP_TOKEN` para entrar.

## AgentOS API

Todos os endpoints usam a mesma autenticação do DevPilot:

- `GET /api/agentos/agents` — catálogo de agentes especialistas;
- `POST /api/agentos/goals` — transforma um objetivo em grafo;
- `GET /api/agentos/goals/{id}` — recupera o plano do objetivo;
- `POST /api/agentos/goals/{id}/executions` — inicia execução idempotente do grafo;
- `GET /api/agentos/executions/{id}` — retorna estado, tentativas, outputs e checkpoints;
- `POST /api/agentos/executions/{id}/steps/{step}/approve` — libera um approval gate;
- `POST /api/agentos/executions/{id}/resume` — retoma execução falha/compensada;
- `POST /api/agentos/knowledge` — quebra conteúdo em chunks, gera embeddings e persiste;
- `POST /api/agentos/rag/query` — busca semântica local;
- `POST /api/agentos/chat` — RAG + modelo generativo via gateway local.

Exemplo de objetivo:

```json
{
  "title": "RAG do RegulaAI",
  "objective": "Implementar RAG para documentos regulatórios com API, testes e deploy controlado"
}
```

Depois de criar o objetivo, inicie sua execução:

```json
{
  "idempotency_key": "regulaai-rag-v1",
  "max_attempts": 3
}
```

O `idempotency_key` evita criar duas execuções quando um cliente repete a mesma requisição.
Se omitido, o AgentOS deriva uma chave determinística do workspace e do objetivo.

## Como o executor funciona

O fluxo padrão é:

```text
Planner -> Researcher? -> Architect -> Backend/Frontend -> Reviewer -> QA -> Delivery?
```

Cada passo persiste status, tentativa, comando, output, checkpoint e erro. Falhas transitórias
entram em `retry_wait` com backoff exponencial limitado. Quando as tentativas terminam, a
execução entra em compensação Saga. Compensação é conservadora: trabalho pendente pode ser
bloqueado, mas branches já executadas são preservadas para revisão em vez de sofrer rollback
destrutivo automático.

Etapas de delivery continuam aguardando aprovação explícita. `resume` nunca ignora esse gate.

## MCP

O servidor MCP expõe somente ferramentas de leitura/planejamento nesta etapa. Push, merge e
deploy continuam atrás das políticas e aprovações do DevPilot.

```bash
python -m app.mcp_server
```

Para desenvolvimento com o MCP Inspector:

```bash
mcp dev app/mcp_server.py
```

Ferramentas iniciais: `list_agents`, `plan_software_goal` e `search_knowledge`.

## Modelos locais e APIs generativas

O AgentOS conversa com Ollama via HTTP. As configurações principais são:

```text
DEVPILOT_OLLAMA_BASE_URL=http://127.0.0.1:11434
DEVPILOT_OLLAMA_CHAT_MODEL=gemma3:1b
DEVPILOT_OLLAMA_EMBEDDING_MODEL=embeddinggemma
```

Troque os nomes pelos modelos instalados na máquina. Em máquinas pequenas, mantenha o
modelo fora do processo FastAPI: o serviço web continua leve e o runtime do modelo pode ser
reiniciado ou substituído independentemente.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Se o Ollama estiver rodando no host e o DevPilot dentro de container, ajuste
`DEVPILOT_OLLAMA_BASE_URL` para um endereço alcançável pelo container.

Antes de produção, gere uma chave Fernet e configure `DEVPILOT_ENCRYPTION_KEY`:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Mantenha `DEVPILOT_EXECUTION_ENABLED=false` até o host do worker ter Codex CLI e Git
configurados, credenciais de escopo mínimo e diretório isolado. Nesse modo, tarefas delegadas
são registradas e executadas como dry-run; o grafo e seus checkpoints ainda podem ser testados.

## Fluxo de uma tarefa

1. Cliente dita ou escreve o objetivo.
2. DevPilot registra o objetivo e o AgentOS gera o grafo.
3. Uma execução persistente é criada com chave de idempotência.
4. O worker executa agentes conforme dependências e checkpoints.
5. Etapas de `repo.write` viram tarefas DevPilot em branches isoladas.
6. Revisor e QA recebem os outputs anteriores como contexto.
7. Falhas usam retry; falhas terminais acionam compensação.
8. Delivery aguarda aprovação humana.
9. Push/PR/deploy permanecem etapas separadas e explicitamente aprovadas.

## Próximas etapas do AgentOS

- memória em níveis global, projeto, objetivo e tarefa;
- adaptadores adicionais de provedores de LLM/embeddings;
- ingestão automática dos repositórios RegulaAI, Máquina de Leads e TelaViva;
- tool registry com permissões por agente;
- cliente MCP para consumir ferramentas externas;
- eventos ao vivo por SSE/WebSocket;
- limites de RAM, CPU, tokens e custo por agente;
- scheduler com fairness para múltiplas execuções;
- avaliação automática de qualidade de respostas RAG e execuções.

## Próximas etapas para produção

- autenticação OIDC e organizações com RBAC;
- migrations Alembic e backups automatizados;
- GitHub App com webhooks e tokens de instalação;
- OpenAI Realtime/WebRTC e transcrição server-side;
- runners efêmeros por tarefa e limites de custo;
- cobrança por workspace, assentos e minutos de execução;
- observabilidade OpenTelemetry, SLOs e alertas;
- análise de segurança e qualidade em PRs.

## Segurança

Nunca envie chaves ao frontend após o cadastro. Em produção, use um KMS/secret manager,
tokens curtos para GitHub Apps, runners sem privilégios e aprovação explícita para push,
merge, deploy, dependências e operações destrutivas. Tarefas de implementação delegadas pelo
AgentOS recebem instruções explícitas para não alterar dependências, credenciais, migrations
destrutivas, configuração de deploy ou recursos de produção sem aprovação.