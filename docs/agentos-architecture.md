# AgentOS architecture

AgentOS is a bounded context inside DevPilot. The implementation follows SOLID, Clean
Architecture and Hexagonal Architecture while staying a modular monolith so it remains
comfortable on a 4 GB Linux development machine.

## Dependency rule

```text
FastAPI / MCP / CLI                  driving adapters
        |
        v
application services + ports        use cases
        |
        v
domain events / state rules         framework-free core
        ^
        |
SQLAlchemy / Ollama / audit          driven adapters
        ^
        |
container.py                         composition root
```

Dependencies point inward. Application services do not import FastAPI, SQLAlchemy, Ollama or
HTTP clients. Provider and persistence details implement small ports and are wired in the
composition root.

## Layers

### Domain

`app/agentos/domain`

Contains framework-free events and execution state rules. `domain/execution.py` defines the
execution and step state machines and rejects illegal transitions. The domain layer must not
depend on FastAPI, SQLAlchemy, HTTP clients or provider SDKs.

### Application

`app/agentos/application`

Contains use cases, ports, planning strategies and the graph coordinator. Main services:

- `GoalService`: plan and persist goals;
- `KnowledgeService`: ingest and retrieve knowledge;
- `ChatService`: run RAG-backed chat through a model port;
- `GraphExecutionService`: execute a dependency graph one checkpoint at a time.

Ports apply Interface Segregation: planning, persistence, command execution, knowledge,
model access, event publishing and transaction control are independent interfaces.

### Infrastructure

`app/agentos/infrastructure`

Contains driven adapters:

- `SQLAlchemyGoalRepository`;
- `SQLAlchemyExecutionRepository`;
- `SQLAlchemyKnowledgeAdapter`;
- `OllamaLanguageModelAdapter`;
- `CompositeCommandRunner`;
- `SQLAlchemyUnitOfWork`;
- `LocalEventBus`;
- `AuditEventHandler`.

The in-process event bus intentionally avoids Redis/Kafka for the local profile. A broker can
replace it later by implementing the same event port.

### Driving adapters

`app/agentos/router.py`, `app/mcp_server.py` and `app/worker.py` translate external requests or
worker ticks into application use cases. Business workflows stay out of these adapters.

### Composition root

`app/agentos/container.py` is the only place responsible for wiring concrete adapters into
application services. This keeps dependency construction explicit and testable.

## Graph execution

A planned goal can be started as a persistent execution. Each step has its own status,
attempt counter, idempotency key, command payload, output and checkpoint. The worker advances
only one command/state transition at a time, which keeps RAM usage bounded and makes crashes
recoverable.

```text
pending -> running -> completed
              |  \
              |   -> waiting_external -> completed
              |             |
              |             -> retry_wait -> pending
              |
              -> retry_wait -> pending
              |
              -> failed -> compensating -> compensated

running -> awaiting_approval -> running
```

Repository-writing backend/frontend steps are delegated to the existing DevPilot task runner.
That preserves the existing isolated-branch executor and its no-push/no-merge boundary. Pure
planning, architecture, review and QA steps are handled through the language-model port.
Delivery remains an explicit approval gate.

## Reliability patterns

### Command

Every step becomes an `AgentCommand`. `CompositeCommandRunner` selects the concrete command
adapter. Adding another executor later does not change the graph coordinator.

### State Machine

`ExecutionStateMachine` owns valid execution and step transitions. Illegal transitions fail
fast instead of silently corrupting orchestration state.

### Saga

When a step exhausts its retries, the coordinator enters `compensating` and invokes
compensation in reverse over completed commands. Compensation is deliberately conservative:
pending delegated work can be blocked, while already executed isolated branch work is
preserved for review rather than destructively reverted.

### Idempotency

Starting the same goal with the same workspace/idempotency key returns the existing execution.
Step-level keys are persisted too, so the design has a stable seam for stricter distributed
idempotency when external brokers/runners are introduced.

### Retry and checkpoint/resume

Failures use bounded exponential backoff. Every completed or delegated step persists a
checkpoint. A failed/compensated execution can be resumed explicitly, optionally resetting
attempt counters. Approval gates are not bypassed by resume; they must be approved through
the dedicated endpoint.

## Applied patterns

- **Strategy**: planning behavior implements a stable planning contract.
- **Factory/Registry**: planning strategies are selected through a registry.
- **Command**: graph steps are represented as executable commands.
- **State Machine**: execution and step lifecycle rules are explicit.
- **Saga**: terminal failures trigger best-effort compensation.
- **Adapter**: Ollama, SQLAlchemy and task execution are hidden behind application ports.
- **Repository**: goal/execution persistence is isolated from use cases.
- **Unit of Work**: transaction commit/rollback is abstracted from use cases.
- **Observer / Pub-Sub**: domain events are dispatched by `LocalEventBus`.
- **Facade**: `orchestrator.plan_goal` remains a compatibility facade.
- **Dependency Injection**: `build_agentos_services` composes dependencies.

## SOLID mapping

- **S — Single Responsibility:** routes translate HTTP, services coordinate use cases,
  repositories persist, command runners execute, state machines validate transitions.
- **O — Open/Closed:** new planning strategies, model adapters or command runners can be added
  without changing graph use cases.
- **L — Liskov Substitution:** tests use lightweight implementations of the same ports.
- **I — Interface Segregation:** ports are small and capability-specific.
- **D — Dependency Inversion:** application services depend on protocols, not Ollama,
  SQLAlchemy, Codex or audit implementations.

## Evolution path

Keep AgentOS as a modular monolith until scaling pressure is measurable. If a component needs
independent scaling later, the existing port boundary is the extraction seam. Likely first
candidates are model execution, repository runners and asynchronous event processing. A future
broker can consume the same persisted execution/checkpoint model without changing the domain
state machine.