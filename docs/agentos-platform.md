# AgentOS platform

AgentOS is organized as a six-layer, resource-light operating model for agents. The layers
remain inside the DevPilot modular monolith so the development profile stays suitable for a
4 GB Linux machine while preserving extraction seams through ports/adapters.

## 1. Kernel

The kernel owns resource and safety policy. The default `resource-light` budget allows one
active agent at a time, disables parallel execution, caps council membership at five agents,
caps hierarchical recall at eight matches, limits council context to 40,000 characters, and
bounds repository intelligence to 400 files, 100,000 characters per file and 2,000,000 total
characters per snapshot.

The kernel also exposes invariant safety facts: delivery requires human approval, push/merge/
deploy are never automatic, council decisions are advisory only, and the built-in extension
marketplace never downloads executable extension code.

## 2. Runtime

The runtime is the persistent graph executor. It advances one command or state transition at a
time and uses checkpoints, idempotency keys, bounded retry, explicit approval gates and Saga
compensation. Repository-writing commands are delegated to isolated DevPilot tasks/branches.

Before a graph command executes, the runtime asks ToolHub to authorize every declared tool for
the current agent and project. When a project has activated extension packs, those activations
become an additional capability boundary: an agent or tool not present in an enabled pack is
denied. Global tool authorization and human approval requirements are still checked afterwards.

## 3. MemoryOS

MemoryOS uses the existing knowledge/embedding port with hierarchical namespaces:

- `memory/global`
- `memory/project/{project_id}`
- `memory/goal/{goal_id}`
- `memory/task/{task_id}`

Recall searches from the most specific scope toward global memory, de-duplicates results and
returns the highest-scoring matches within the kernel budget. Memory writes are transactional
and emit `agentos.memory.ingested` audit events.

Repository intelligence uses separate immutable snapshot namespaces such as
`repo/{project_id}/{snapshot_hash}`. Only the namespace recorded in `agent_repository_indexes`
is considered the current code index, so re-indexing an unchanged repository is a no-op and a
changed repository gets a new version without mixing old and current chunks.

## 4. ToolHub

ToolHub is the capability registry and authorization boundary. Every registered tool declares:

- risk level (`read`, `isolated-write`, or `controlled`);
- allowed agents;
- whether explicit human approval is required.

The registry now includes `repo.index` and `code.impact` in addition to planning, RAG/project
reads, repository reads/writes, tests, diff/test evidence, CI reads and deployment planning.
There is no automatic push, merge or deployment capability in the registry.

### Specialist agents

The catalog includes the original Supervisor, Planner, Researcher, Architect, Backend, Frontend,
Reviewer, QA and DevOps agents plus five focused specialists:

- **Database** — schema, migrations, query behavior and data integrity;
- **Security** — authentication, authorization, secrets and attack surface;
- **Performance** — memory, latency, query cost and resource-budget regressions;
- **UX** — journeys, accessibility and interaction clarity;
- **Docs** — architecture, runbooks, API documentation and living change notes.

Each specialist has a bounded default tool set. Project extension activations can reduce that
surface further.

## 5. AppHub

AppHub exposes DevPilot projects as AgentOS applications through an application port. The
SQLAlchemy adapter returns project identity, description, repository URL and status without
exposing provider credentials, Git credentials or environment secrets.

AgentOS has curated, versioned connection profiles for the first three product apps:

- **RegulaAI** — regulatory intelligence, idempotent collectors, regulatory precision and
  PostgreSQL history/guardrails;
- **Máquina de Leads** — campaign-first prospecting, native backend orchestration and gradual
  removal of n8n from the critical path;
- **TelaViva** — live learning/creator commerce with authorization, WebSocket, payment and
  recording lifecycle constraints.

`POST /api/agentos/apps/connect-known` creates missing DevPilot projects for those repositories
without overwriting an existing project bound to another repository. Every connection is stored
in `agent_app_connections` with separate profile and MemoryOS versions.

The bootstrap request can now optionally activate recommended extension packs and index the
repository immediately. Extension activation defaults on; repository indexing remains opt-in so
a lightweight local installation does not unexpectedly clone/fetch three repositories.

Example:

```json
{
  "keys": ["regulaai", "maquinadeleads", "telaviva"],
  "seed_memory": true,
  "activate_recommended_extensions": true,
  "index_repositories": true,
  "refresh_repositories": false
}
```

Known app registration never writes `AGENTS.md` into a repository. Existing repository-specific
instructions remain authoritative when the isolated DevPilot worker clones and executes the
project.

## Repository Intelligence

Repository Intelligence provides bounded code/document understanding without loading a large ML
framework into the FastAPI process. It reads text files from the isolated DevPilot repository
workspace, excludes common generated/cache directories and secret-bearing `.env` files, hashes
each document, and creates a stable repository snapshot hash.

The service indexes code, Markdown/docs, SQL and configuration text into the current repository
RAG namespace. A manifest includes file count and dependency graph statistics. Indexing is
idempotent by snapshot hash and emits `agentos.repository.indexed`.

A lightweight dependency graph is derived from Python imports and relative JavaScript/TypeScript
imports. `code.impact` can then return direct dependencies and reverse dependencies up to the
kernel impact-depth limit before an implementation agent edits a file. This is an impact aid,
not a replacement for tests or review.

HTTP surface:

- `GET /api/agentos/intelligence/{project_id}` — current index metadata;
- `POST /api/agentos/intelligence/{project_id}/index` — bounded index/refresh;
- `POST /api/agentos/intelligence/{project_id}/search` — semantic search in the current snapshot;
- `POST /api/agentos/intelligence/{project_id}/impact` — static dependency/reverse-impact report.

## Safe Extension Marketplace

The first marketplace is deliberately a reviewed built-in catalog rather than a remote code
loader. Activating a pack stores project-scoped state in `agent_extension_activations`; it never
installs Python packages, downloads plugins or changes dependencies.

Built-in packs:

- `software-core` — normal planning, architecture, implementation, review and QA;
- `assurance` — Database, Security and Performance specialists;
- `product-experience` — UX and Docs specialists;
- `operations` — Supervisor/DevOps with CI reads and approval-gated deployment planning.

HTTP surface:

- `GET /api/agentos/marketplace` — reviewed extension catalog;
- `GET /api/agentos/marketplace/activations` — project activation state;
- `POST /api/agentos/marketplace/{project_id}/{extension_key}` — enable/disable a built-in pack.

## 6. Interfaces

FastAPI and MCP remain driving adapters. The broader HTTP surface includes platform, agents,
tools, apps, goals/executions, MemoryOS, repository intelligence, marketplace and council
operations. The worker remains sequential in the 4 GB profile.

## Council of Agents

The council runs sequentially to respect the 4 GB profile. The default members are Planner,
Architect and Reviewer. Each member receives the same bounded RAG context and returns a
structured vote: `approve`, `reject` or `abstain`, plus confidence and rationale.

Votes are confidence-weighted. If the winning side does not reach the requested consensus
threshold, the result is `human_review`. Even when the council returns `approve`, the response
contains `advisory_only=true`; it cannot satisfy a delivery approval gate or authorize push,
merge, deployment, dependency changes, destructive migrations or production actions.

Council deliberations emit `agentos.council.deliberated` audit events containing the decision,
consensus, members and RAG match count, without converting the advisory result into an
operational approval.
