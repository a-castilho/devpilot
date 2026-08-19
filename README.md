# DevPilot AgentOS — seu desenvolvedor e orquestrador de agentes

DevPilot é um SaaS leve para automatizar desenvolvimento de software por dashboard, API,
voz ou agentes. Ele organiza múltiplos projetos e tarefas, aplica instruções `AGENTS.md`,
controla configurações do Codex, executa trabalho em branches isoladas e registra cada
decisão em uma trilha de auditoria encadeada por hash.

A partir da versão 1.1, o DevPilot também contém o núcleo **AgentOS**: catálogo de agentes,
planejamento em grafo, memória/RAG local, gateway para modelos generativos e embeddings via
Ollama e uma interface MCP para que outros hosts de IA consumam essas capacidades.

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
        ├── AgentOS supervisor / planner / specialists
        │        │
        │        ├── goal graph
        │        ├── RAG / embeddings ── SQLite
        │        └── model gateway ── Ollama HTTP ── transformer model
        │
        ├── PostgreSQL/SQLite
        └── vault criptografado

worker ── projeto isolado ── Codex CLI ── Git branch/PR
```

O plano do AgentOS é determinístico por padrão. Isso mantém o plano de controle disponível
mesmo quando nenhum modelo está carregado. O LLM entra onde agrega valor — conversa,
interpretação e síntese — sem ser requisito para o sistema iniciar.

## Perfil para Linux com 4 GB de RAM

Para desenvolvimento local de baixo consumo, prefira:

1. SQLite (`DEVPILOT_DATABASE_URL=sqlite:///./data/devpilot.db`);
2. API e worker em processos separados, iniciando o worker apenas quando precisar executar;
3. Ollama nativo no host, com um modelo de chat pequeno configurável;
4. `embeddinggemma` (ou outro modelo de embeddings disponível no seu Ollama) para RAG;
5. uma tarefa/agente executando por vez;
6. Docker/PostgreSQL apenas quando estiver validando o ambiente de produção.

Se o serviço de embeddings estiver indisponível, o AgentOS possui um embedding hashing de
256 dimensões como fallback operacional. Ele mantém busca básica funcionando, mas não
substitui um embedding semântico baseado em transformer.

## Executar localmente

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8080
```

Em outro terminal, quando precisar executar tarefas de desenvolvimento:

```bash
source .venv/bin/activate
python -m app.worker
```

Abra `http://localhost:8080` e use o valor de `DEVPILOT_BOOTSTRAP_TOKEN` para entrar.

## AgentOS API

Todos os endpoints usam a mesma autenticação do DevPilot:

- `GET /api/agentos/agents` — catálogo de agentes especialistas;
- `POST /api/agentos/goals` — transforma um objetivo em grafo de execução;
- `GET /api/agentos/goals/{id}` — recupera plano e estado do objetivo;
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

## MCP

O servidor MCP expõe somente ferramentas de leitura/planejamento nesta primeira etapa. Push,
merge e deploy continuam atrás das políticas e aprovações do DevPilot.

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
configurados, credenciais de escopo mínimo e diretório isolado.

## Fluxo de uma tarefa

1. Cliente dita ou escreve o objetivo.
2. DevPilot registra transcript/prompt e avalia risco.
3. AgentOS decompõe o objetivo em um grafo de agentes e dependências.
4. Ações sensíveis aguardam aprovação.
5. O worker cria uma branch exclusiva e chama o executor configurado.
6. Revisor e QA validam a saída antes de qualquer etapa de entrega.
7. Testes, logs e resumo ficam associados à execução.
8. Push/PR/deploy permanecem etapas separadas e explicitamente aprovadas.

## Próximas etapas do AgentOS

- executor real do grafo com estados por etapa e retomada após falha;
- memória em níveis global, projeto, objetivo e tarefa;
- adaptadores adicionais de provedores de LLM/embeddings;
- ingestão automática dos repositórios RegulaAI, Máquina de Leads e TelaViva;
- tool registry com permissões por agente;
- cliente MCP para consumir ferramentas externas;
- eventos ao vivo por SSE/WebSocket;
- limites de RAM, CPU, tokens e custo por agente;
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
merge, deploy, dependências e operações destrutivas. O AgentOS mantém o MCP inicial em modo
read/plan justamente para que a expansão de ferramentas ocorra com políticas explícitas.
