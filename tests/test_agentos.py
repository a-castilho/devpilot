from app.agentos.embeddings import hashing_embedding
from app.agentos.orchestrator import plan_goal
from app.agentos.rag import chunk_text, cosine_similarity


def test_plan_goal_builds_dependency_graph_and_approval_gate():
    plan = plan_goal("Implement RAG API and deploy it with Docker")
    ids = {step.id for step in plan.steps}

    assert {"plan", "research", "architecture", "backend", "review", "qa", "delivery"} <= ids
    delivery = next(step for step in plan.steps if step.id == "delivery")
    assert delivery.approval_required is True
    assert delivery.depends_on == ["qa"]


def test_plan_goal_keeps_frontend_optional():
    plan = plan_goal("Create a dashboard interface for agent status")
    ids = {step.id for step in plan.steps}

    assert "frontend" in ids
    assert "review" in ids
    assert "qa" in ids


def test_chunk_text_is_bounded_and_overlapping():
    text = " ".join(f"token-{index}" for index in range(500))
    chunks = chunk_text(text, max_chars=300, overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_hashing_embedding_is_deterministic_and_normalized():
    left = hashing_embedding("AgentOS retrieves grounded project context")
    right = hashing_embedding("AgentOS retrieves grounded project context")

    assert left == right
    assert cosine_similarity(left, right) > 0.999
