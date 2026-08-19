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
domain events / domain rules        framework-free core
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

Contains immutable domain events and future framework-free entities/value objects. This layer
must not depend on FastAPI, SQLAlchemy, HTTP clients or provider SDKs.

### Application

`app/agentos/application`

Contains use cases, ports and planning strategies. The main services are:

- `GoalService`: plan and persist goals;
- `KnowledgeService`: ingest and retrieve knowledge;
- `ChatService`: run RAG-backed chat through a model port.

Ports apply Interface Segregation: planning, goal persistence, knowledge, model access, event
publishing and transaction control are independent interfaces.

### Infrastructure

`app/agentos/infrastructure`

Contains driven adapters:

- `SQLAlchemyGoalRepository`;
- `SQLAlchemyKnowledgeAdapter`;
- `OllamaLanguageModelAdapter`;
- `SQLAlchemyUnitOfWork`;
- `LocalEventBus`;
- `AuditEventHandler`.

The in-process event bus intentionally avoids Redis/Kafka for the local profile. A broker can
replace it later by implementing the same event port.

### Driving adapters

`app/agentos/router.py` and `app/mcp_server.py` translate external requests into application
use cases. Business workflows should not be implemented in these adapters.

### Composition root

`app/agentos/container.py` is the only place responsible for wiring concrete adapters into
application services. This keeps dependency construction explicit and testable.

## Applied patterns

- **Strategy**: planning behavior implements a stable `PlanningStrategy` contract.
- **Factory/Registry**: `PlanningStrategyFactory` selects and can register planning strategies.
- **Adapter**: Ollama and SQLAlchemy are hidden behind application ports.
- **Repository**: goal persistence is isolated behind `GoalRepositoryPort`.
- **Unit of Work**: transaction commit/rollback is abstracted from use cases.
- **Observer / Pub-Sub**: domain events are dispatched by `LocalEventBus`.
- **Facade**: `orchestrator.plan_goal` remains as a compatibility facade while callers migrate.
- **Dependency Injection**: `build_agentos_services` composes all dependencies.

## SOLID mapping

- **S — Single Responsibility:** routes translate HTTP, services coordinate use cases,
  repositories persist, adapters integrate providers.
- **O — Open/Closed:** new planning strategies or model adapters can be added without changing
  the goal/chat use cases.
- **L — Liskov Substitution:** tests use lightweight fake implementations of the same ports.
- **I — Interface Segregation:** ports are small and capability-specific.
- **D — Dependency Inversion:** application services depend on protocols, not Ollama,
  SQLAlchemy or audit implementations.

## Evolution path

Keep AgentOS as a modular monolith until scaling pressure is measurable. If a component needs
independent scaling later, the existing port boundary is the extraction seam. The first likely
candidates are model execution, repository runners and asynchronous event processing.
