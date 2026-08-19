from app.agentos.contracts import AgentDefinition


AGENT_CATALOG: dict[str, AgentDefinition] = {
    "supervisor": AgentDefinition(
        name="supervisor",
        role="orchestration",
        description="Controls execution, budgets, approvals and final handoff.",
        capabilities=["orchestrate", "prioritize", "stop", "approve-gates"],
        default_tools=["agent.plan", "audit.read"],
    ),
    "planner": AgentDefinition(
        name="planner",
        role="planning",
        description="Turns a natural-language objective into an explicit dependency graph.",
        capabilities=["decompose", "estimate", "sequence"],
        default_tools=["rag.search", "project.read"],
    ),
    "researcher": AgentDefinition(
        name="researcher",
        role="research",
        description="Retrieves project and knowledge-base context before implementation.",
        capabilities=["retrieve", "summarize", "compare"],
        default_tools=["rag.search", "project.read"],
    ),
    "architect": AgentDefinition(
        name="architect",
        role="architecture",
        description="Defines boundaries, contracts and non-functional constraints.",
        capabilities=["design", "threat-model", "contract-design"],
        default_tools=["rag.search", "project.read"],
    ),
    "backend": AgentDefinition(
        name="backend",
        role="implementation",
        description="Implements APIs, domain logic, persistence and integrations.",
        capabilities=["python", "fastapi", "sql", "integrations"],
        default_tools=["repo.read", "repo.write", "tests.run"],
    ),
    "frontend": AgentDefinition(
        name="frontend",
        role="implementation",
        description="Implements dashboard and client-side interactions.",
        capabilities=["ui", "pwa", "accessibility", "api-client"],
        default_tools=["repo.read", "repo.write", "tests.run"],
    ),
    "reviewer": AgentDefinition(
        name="reviewer",
        role="quality",
        description="Reviews changes for correctness, security and maintainability.",
        capabilities=["code-review", "security-review", "performance-review"],
        default_tools=["repo.read", "diff.read", "tests.read"],
    ),
    "qa": AgentDefinition(
        name="qa",
        role="verification",
        description="Creates and executes verification against acceptance criteria.",
        capabilities=["test-design", "regression", "acceptance"],
        default_tools=["tests.run", "repo.read"],
    ),
    "devops": AgentDefinition(
        name="devops",
        role="delivery",
        description="Prepares controlled build, release and deployment actions.",
        capabilities=["docker", "ci", "deploy", "rollback"],
        default_tools=["ci.read", "deploy.plan"],
    ),
}
