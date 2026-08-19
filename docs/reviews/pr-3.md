# Revisão PR #3 — feat: AgentOS platform, live provider catalogs and local execution

> Relatório gerado automaticamente.

## Metadados

- **Estado:** Aberta
- **Autor:** @acastilho
- **Base:** `main`
- **Head:** `feat/agentos-core`
- **Atualizada em:** 2026-08-19T20:42:51Z
- **Fonte:** https://github.com/a-castilho/devpilot/pull/3

## Sinais automáticos de revisão

- **Referência de issue detectada:** NÃO
- **Mudança de UI provável:** SIM
- **Evidência visual detectada:** NÃO
- **Arquivos alterados:** 70

> Se houver UI provável sem evidência visual, a revisão deve pedir screenshot/registro ou justificativa explícita.

## Arquivos alterados

- `.env.example` (+25/-0)
- `AGENTS.md` (+17/-0)
- `README.md` (+169/-25)
- `app/agentos/__init__.py` (+6/-0)
- `app/agentos/application/__init__.py` (+6/-0)
- `app/agentos/application/app_connections.py` (+143/-0)
- `app/agentos/application/errors.py` (+10/-0)
- `app/agentos/application/execution.py` (+348/-0)
- `app/agentos/application/extensions.py` (+90/-0)
- `app/agentos/application/intelligence.py` (+194/-0)
- `app/agentos/application/planning.py` (+198/-0)
- `app/agentos/application/platform.py` (+414/-0)
- `app/agentos/application/ports.py` (+227/-0)
- `app/agentos/application/services.py` (+220/-0)
- `app/agentos/apps_router.py` (+108/-0)
- `app/agentos/catalog.py` (+103/-0)
- `app/agentos/container.py` (+130/-0)
- `app/agentos/contracts.py` (+106/-0)
- `app/agentos/domain/__init__.py` (+5/-0)
- `app/agentos/domain/apps.py` (+118/-0)
- `app/agentos/domain/events.py` (+23/-0)
- `app/agentos/domain/execution.py` (+115/-0)
- `app/agentos/domain/extensions.py` (+50/-0)
- `app/agentos/domain/intelligence.py` (+73/-0)
- `app/agentos/domain/platform.py` (+125/-0)
- `app/agentos/embeddings.py` (+59/-0)
- `app/agentos/infrastructure/__init__.py` (+1/-0)
- `app/agentos/infrastructure/adapters.py` (+296/-0)
- `app/agentos/infrastructure/execution.py` (+318/-0)
- `app/agentos/infrastructure/extensions.py` (+71/-0)
- `app/agentos/infrastructure/intelligence.py` (+273/-0)
- `app/agentos/infrastructure/platform.py` (+152/-0)
- `app/agentos/intelligence_router.py` (+162/-0)
- `app/agentos/llm.py` (+50/-0)
- `app/agentos/models.py` (+140/-0)
- `app/agentos/orchestrator.py` (+15/-0)
- `app/agentos/rag.py` (+139/-0)
- `app/agentos/router.py` (+366/-0)
- `app/api.py` (+179/-5)
- `app/config.py` (+25/-0)
- `app/main.py` (+10/-2)
- `app/mcp_server.py` (+72/-0)
- `app/preflight.py` (+150/-0)
- `app/provider_runtime_router.py` (+110/-0)
- `app/schemas.py` (+5/-0)
- `app/services/executor.py` (+88/-14)
- `app/services/local_executor.py` (+300/-0)
- `app/services/provider_models.py` (+211/-0)
- `app/services/provider_runtime.py` (+281/-0)
- `app/static/app.js` (+12/-4)
- `app/static/index.html` (+4/-1)
- `app/static/provider-models.css` (+28/-0)
- `app/static/results.css` (+3/-0)
- `app/worker.py` (+45/-3)
- `docs/agentos-architecture.md` (+170/-0)
- `docs/agentos-platform.md` (+174/-0)
- `docs/local-execution.md` (+104/-0)
- `docs/provider-models.md` (+94/-0)
- `pyproject.toml` (+3/-2)
- `tests/test_agentos.py` (+38/-0)
- `tests/test_agentos_app_connections.py` (+158/-0)
- `tests/test_agentos_architecture.py` (+100/-0)
- `tests/test_agentos_execution.py` (+157/-0)
- `tests/test_agentos_intelligence.py` (+224/-0)
- `tests/test_agentos_model_gateway.py` (+177/-0)
- `tests/test_agentos_platform.py` (+250/-0)
- `tests/test_agentos_reliability.py` (+143/-0)
- `tests/test_executor.py` (+166/-0)
- `tests/test_provider_models.py` (+104/-0)
- `tests/test_provider_runtime.py` (+214/-0)

## Descrição e evidências da PR

## Summary

Evolves DevPilot into a resource-light AgentOS for software agents, with persistent graph execution, hierarchical memory, product app connections, repository intelligence, specialist agents, safe extension activation, hardened local execution, and live AI-provider model catalogs.

### AgentOS core
- specialist agent catalog and deterministic dependency-graph planner
- persistent goals, local RAG/embeddings, Ollama chat gateway and MCP v2 read/plan server
- authenticated API with audit/event integration
- SOLID + Clean Architecture + Hexagonal Architecture + DDD bounded context

### Persistent graph runtime
- Command pattern for executable agent work
- explicit execution/step State Machine
- checkpoints and execution/step idempotency
- bounded retry with exponential backoff
- Saga compensation after terminal failures
- explicit resume for failed/compensated runs
- approval gates that cannot be bypassed by retry/resume
- backend/frontend repository writes delegated to isolated DevPilot tasks/branches

### Six-layer AgentOS platform
1. Kernel — resource budgets and safety invariants
2. Runtime — persistent sequential graph execution
3. MemoryOS — hierarchical global/project/goal/task memory
4. ToolHub — capability registry and authorization boundary
5. AppHub — DevPilot projects exposed as AgentOS applications
6. Interfaces — FastAPI/MCP/dashboard/voice driving adapters

### Product app connections
- curated profiles for RegulaAI, Máquina de Leads and TelaViva
- idempotent AppHub project registration
- project-scoped MemoryOS seed with product context, stack and guardrails
- optional bootstrap of recommended extension packs and repository indexing
- repository/slug conflicts fail closed
- repository-specific AGENTS.md is never overwritten

### Repository Intelligence
- bounded local repository snapshotting for code/docs/configuration
- ignores common generated/cache directories and secret-bearing files
- immutable snapshot namespaces with persisted current-index metadata
- idempotent indexing by repository snapshot hash
- RAG search over the current repository snapshot
- lightweight Python and JS/TS dependency graph
- reverse-impact analysis before code edits
- audited as agentos.repository.indexed

### Hardened local task execution
- `DEVPILOT_TASK_EXECUTOR=auto` routes explicit read-only tasks to local Ollama and write tasks to Codex
- read-only execution reads committed content directly from `origin/<default_branch>` without checking out a task branch
- configured project `agents_md` is injected as policy instead of being written into the repository
- `.env`, private-key formats, credential/secret files, generated directories and oversized blobs are excluded from local context
- resource-light context budget defaults to 40 files / 8k chars per file / 40k total chars
- worktree status is verified unchanged before/after local read-only analysis
- Ollama failures fail closed with actionable diagnostics; no mutating fallback is used
- Codex JSONL errors are parsed into human-readable run summaries, including quota/provider errors
- worker emits safe progress/status lines without task prompts or provider secrets
- `python -m app.preflight` checks Python, Git, Codex, Ollama/model availability and execution configuration

### Live provider model catalogs
- clicking **Conectar IA** refreshes catalogs for saved OpenAI, Anthropic and Google Gemini connections
- provider selection immediately renders the current cached/live catalog for that provider
- first-time connections can query the official provider API with the entered API key before saving
- saving validates the credential and selected model IDs against the provider's live catalog
- no model selection means all currently available models returned for that credential are stored
- OpenAI uses `GET /v1/models`, Anthropic uses `GET /v1/models`, and Gemini uses `GET /v1beta/models`
- Google embedding-only entries are excluded from the generative-model selector
- custom providers remain manual until DevPilot has a trustworthy per-provider base URL/discovery contract
- discovery errors are sanitized; provider response bodies and API keys are never written to audit logs

### Task result UX/API
- `GET /api/tasks/{task_id}/runs` exposes workspace-scoped execution results
- dashboard shows `Resultado` for review/completed/failed tasks
- result dialog exposes run summary, executor/provider/model/ref metadata and bounded output

### Specialist agents
Adds Database, Security, Performance, UX and Docs specialists with bounded tool sets alongside Planner, Researcher, Architect, Backend, Frontend, Reviewer, QA, DevOps and Supervisor.

### Safe Extension Marketplace
- reviewed built-in packs only; no remote executable extension downloads
- project-scoped persisted activations
- software-core, assurance, product-experience and operations packs
- enabled packs become an additional ToolHub capability boundary
- global per-agent tool authorization still applies
- deploy.plan remains explicit-human-approval gated

### Expanded Kernel budget
The 4 GB profile caps repository files, per-file characters, total indexed characters, impact depth and execution time while continuing to allow only one active agent at a time.

### HTTP surface additions
- `GET /api/agentos/intelligence/{project_id}`
- `POST /api/agentos/intelligence/{project_id}/index`
- `POST /api/agentos/intelligence/{project_id}/search`
- `POST /api/agentos/intelligence/{project_id}/impact`
- `GET /api/agentos/marketplace`
- `GET /api/agentos/marketplace/activations`
- `POST /api/agentos/marketplace/{project_id}/{extension_key}`
- extended `POST /api/agentos/apps/connect-known` bootstrap options
- `GET /api/tasks/{task_id}/runs`
- `GET /api/providers/model-catalog?refresh=true`
- `POST /api/providers/discover-models`

## Safety
- no automatic push, merge or deploy
- delivery still requires explicit human approval
- read-only tasks do not create branches or write configured AGENTS.md into checkouts
- local repository context excludes common secret-bearing files
- AI-provider keys remain encrypted at rest and never return via the API
- model-discovery audit events contain provider/count only, never credentials
- marketplace activation never installs dependencies or downloads executable plugins
- ToolHub denies unregistered, unauthorized or project-disabled capabilities
- worker and council remain sequential for the 4 GB profile

## Documentation
- `docs/agentos-architecture.md`
- `docs/agentos-platform.md`
- `docs/local-execution.md`
- `docs/provider-models.md`

## Validation
- existing AgentOS/executor/repository-intelligence/marketplace tests remain in the suite
- provider discovery tests cover OpenAI, Anthropic and Gemini parsing, Google header-based key transport, duplicate handling, generative-model filtering and sanitized authentication errors
- CI compiles Python sources, runs pytest and builds the Docker image when GitHub can create the pull-request merge ref.

## Comparação obrigatória

1. Issue e critérios de aceite.
2. Diff e arquivos alterados.
3. Resultado observável/tela.
4. Divergências antes do merge.
