from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTIONS = ROOT / "app/static/executions-v18.js"
PROJECTS = ROOT / "app/static/project-delete-ui.js"


def test_ready_project_link_is_available_in_projects_executions_and_overview():
    executions = EXECUTIONS.read_text(encoding="utf-8")
    projects = PROJECTS.read_text(encoding="utf-8")

    # Projetos já possui o contrato canônico e continua sendo a fonte visual da aba.
    assert "function ensureReadyLink(card, project)" in projects
    assert "project-ready-link" in projects
    assert "Abrir projeto ↗" in projects

    # Execuções reutiliza a mesma entrega real do projeto, sem sintetizar domínio.
    assert "function fetchReadyDelivery(projectId)" in executions
    assert "`/projects/${encodeURIComponent(key)}/delivery`" in executions
    assert "readyDelivery(value)" in executions
    assert "project-ready-access-link-execution" in executions
    assert "#tasks-table tr.task-main-row[data-task-id]" in executions

    # A tela inicial expõe somente projetos prontos relacionados à atividade recente.
    assert "function decorateOverviewProjectLinks()" in executions
    assert "#recent-tasks" in executions
    assert "overview-project-ready-links" in executions
    assert "PROJETOS DISPONÍVEIS PARA TESTE" in executions
    assert "project-ready-access-link-overview" in executions


def test_project_access_links_are_safe_and_bounded():
    executions = EXECUTIONS.read_text(encoding="utf-8")

    assert "const DELIVERY_CACHE_TTL_MS = 30000" in executions
    assert "const DELIVERY_VISIBLE_LIMIT = 12" in executions
    assert "const deliveryCache = new Map()" in executions
    assert "const deliveryRequests = new Map()" in executions
    assert "return /^https:\\/\\//i.test(candidate) ? candidate : '';" in executions
    assert "delivery?.status || '').trim().toLowerCase() === 'ready'" in executions
    assert "link.target = '_blank'" in executions
    assert "link.rel = 'noopener noreferrer'" in executions
