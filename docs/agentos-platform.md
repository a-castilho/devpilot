# AgentOS platform

AgentOS is organized as a six-layer, resource-light operating model for agents. The layers
remain inside the DevPilot modular monolith so the development profile stays suitable for a
4 GB Linux machine while preserving extraction seams through ports/adapters.

## 1. Kernel

The kernel owns resource and safety policy. The default `resource-light` budget allows one
active agent at a time, disables parallel execution, caps council membership at five agents,
caps hierarchical recall at eight matches, and limits council context to 40,000 characters.

The kernel also exposes invariant safety facts: delivery requires human approval, push/merge/
deploy are never automatic, and council decisions are advisory only.

## 2. Runtime

The runtime is the persistent graph executor. It advances one command or state transition at a
time and uses checkpoints, idempotency keys, bounded retry, explicit approval gates and Saga
compensation. Repository-writing commands are delegated to isolated DevPilot tasks/branches.

Before a graph command executes, the runtime asks ToolHub to authorize every declared tool for
the current agent. Tool policy failure is terminal for that step and enters the existing
compensation path rather than being retried as a transient provider failure.

## 3. MemoryOS

MemoryOS uses the existing knowledge/embedding port with hierarchical namespaces:

- `memory/global`
- `memory/project/{project_id}`
- `memory/goal/{goal_id}`
- `memory/task/{task_id}`

Recall searches from the most specific scope toward global memory, de-duplicates results and
returns the highest-scoring matches within the kernel budget. Memory writes are transactional
and emit `agentos.memory.ingested` audit events.

## 4. ToolHub

ToolHub is the capability registry and authorization boundary. Every registered tool declares:

- risk level (`read`, `isolated-write`, or `controlled`);
- allowed agents;
- whether explicit human approval is required.

The initial registry covers planning, audit reads, RAG/project reads, repository reads/writes,
test execution, diff/test evidence, CI reads and deployment planning. There is no automatic
push, merge or deployment capability in the registry.

## 5. AppHub

AppHub exposes DevPilot projects as AgentOS applications through an application port. The
SQLAlchemy adapter returns project identity, description, repository URL and status without
exposing provider credentials, Git credentials or environment secrets.

AgentOS also has curated, versioned connection profiles for the first three product apps:

- **RegulaAI** — regulatory intelligence, idempotent collectors, regulatory precision and
  PostgreSQL history/guardrails;
- **Máquina de Leads** — campaign-first prospecting, native backend orchestration and gradual
  removal of n8n from the critical path;
- **TelaViva** — live learning/creator commerce with authorization, WebSocket, payment and
  recording lifecycle constraints.

`POST /api/agentos/apps/connect-known` creates missing DevPilot projects for those repositories
without overwriting an existing project bound to another repository. Every connection is stored
in `agent_app_connections` with separate profile and MemoryOS versions.

On the first connection (or when a future memory profile version increases), AgentOS seeds the
project-scoped MemoryOS namespace with the product context, stack, guardrails and recommended
specialist agents. Repeating the same request is idempotent: it neither creates duplicate
projects nor re-seeds an already-current memory profile.

Known app registration never writes `AGENTS.md` into a repository. Existing repository-specific
instructions remain authoritative when the isolated DevPilot worker clones and executes the
project. This is especially important for Máquina de Leads, whose repository already contains
its own `AGENTS.md` migration and safety rules.

## 6. Interfaces

FastAPI and MCP remain driving adapters. The current HTTP surface includes:

- `GET /api/agentos/platform` — kernel/layer/resource profile;
- `GET /api/agentos/tools` — ToolHub registry, optionally filtered by agent;
- `GET /api/agentos/apps` — AppHub project applications;
- `GET /api/agentos/apps/profiles` — curated product connection profiles;
- `GET /api/agentos/apps/connections` — persisted AppHub/MemoryOS connection state;
- `POST /api/agentos/apps/connect-known` — idempotently connect RegulaAI, Máquina de Leads and
  TelaViva (all or selected profiles);
- `POST /api/agentos/memory` — write scoped MemoryOS content;
- `POST /api/agentos/memory/recall` — hierarchical recall;
- `POST /api/agentos/council` — sequential advisory council deliberation.

Example connection request:

```json
{
  "keys": ["regulaai", "maquinadeleads", "telaviva"],
  "seed_memory": true
}
```

An empty `keys` array means all curated profiles.

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
