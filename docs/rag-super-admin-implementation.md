# DEVpilot RAG + Super Admin

## Objetivo

Implementar uma camada RAG desacoplada do núcleo do DEVpilot, com PostgreSQL + pgvector para recuperação vetorial, Redis para cache, embeddings via API e um painel exclusivo de Super Admin para operação, observabilidade e controle.

## Princípios

- DEVpilot continua funcional com RAG desligado ou degradado.
- Git/GitHub, documentação, banco e auditoria permanecem fontes da verdade.
- RAG é uma camada reconstruível de recuperação de conhecimento.
- Toda consulta é isolada por organização e projeto.
- Frontend nunca acessa Redis, pgvector, GitHub ou provedor de embeddings diretamente.
- O Super Admin controla o RAG por API administrativa.

## Componentes

### Backend

- `RagService`: contrato principal para indexação, retrieval, invalidação e health.
- `RagQueryRouter`: classifica consultas em `NO_RAG`, `RAG`, `LIVE` e `RAG_LIVE`.
- `ContextBuilder`: monta contexto final respeitando orçamento de tokens.
- `EmbeddingProvider`: abstração do provedor de embeddings.
- `RagSanitizer`: remove segredos antes da persistência vetorial.
- `GitSourceAdapter`, `DocsSourceAdapter`, `AuditSourceAdapter`: fontes de ingestão.
- worker de indexação incremental com hash de conteúdo, retry e backpressure.

### Persistência

Tabelas previstas:

- `rag_documents`
- `rag_chunks`
- `rag_index_jobs`
- `rag_queries`

Campos de isolamento obrigatórios: `organization_id` e `project_id`.

### Cache

Redis com namespace `rag:*`, TTL configurável e limite explícito de memória. O cache é descartável e nunca é fonte da verdade.

### Super Admin

Área `RAG / Base de Conhecimento` com:

- visão geral e health;
- ativação/desativação global;
- controles por fonte;
- projetos indexados;
- fila e jobs;
- cache;
- consultas e explicabilidade;
- métricas de tokens/custos;
- auditoria administrativa;
- configurações seguras.

## API administrativa prevista

- `GET /api/super-admin/rag/overview`
- `GET /api/super-admin/rag/health`
- `GET /api/super-admin/rag/projects`
- `GET /api/super-admin/rag/projects/{id}`
- `POST /api/super-admin/rag/projects/{id}/index`
- `POST /api/super-admin/rag/projects/{id}/reindex`
- `POST /api/super-admin/rag/projects/{id}/pause`
- `DELETE /api/super-admin/rag/projects/{id}/index`
- `GET /api/super-admin/rag/jobs`
- `POST /api/super-admin/rag/jobs/{id}/retry`
- `POST /api/super-admin/rag/jobs/{id}/cancel`
- `GET /api/super-admin/rag/queries`
- `GET /api/super-admin/rag/cache`
- `DELETE /api/super-admin/rag/cache`
- `DELETE /api/super-admin/rag/projects/{id}/cache`
- `GET /api/super-admin/rag/costs`
- `GET /api/super-admin/rag/settings`
- `PATCH /api/super-admin/rag/settings`

## Feature flags iniciais

- `RAG_ENABLED=true`
- `RAG_CACHE_ENABLED=true`
- `RAG_GIT_ENABLED=true`
- `RAG_DOCS_ENABLED=true`
- `RAG_AUDIT_ENABLED=false`
- `RAG_TASKS_ENABLED=false`
- `RAG_LOGS_ENABLED=false`

## Rollout

1. Fundação, contratos e migrations.
2. Git + documentação.
3. Retrieval vetorial.
4. Redis.
5. Integração com chat e DEVpilot geral.
6. API administrativa.
7. Front Super Admin.
8. Auditoria, tarefas e incidentes como fontes.
9. Métricas de tokens/custos e tuning.

## Critérios de segurança

- Nunca indexar `.env`, tokens, passwords, private keys, cookies ou connection strings sensíveis.
- Projeto A nunca recupera chunks do Projeto B.
- Ações destrutivas do Super Admin exigem confirmação e são registradas na auditoria existente.

## Requisito low-RAM

Para ambiente com cerca de 4 GB de RAM:

- embeddings via API;
- um worker de indexação;
- batches pequenos;
- Redis limitado;
- `top_k` inicial de 3 a 5;
- nenhuma dependência de modelo local.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

