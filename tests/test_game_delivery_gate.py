from pathlib import Path
from types import SimpleNamespace

from app import delivery_url_recovery as recovery
from app import product_delivery_routes as delivery
from app.delivery_url_recovery import _safe_public_url


ROOT = Path(__file__).resolve().parents[1]


def test_game_mission_ui_requires_verified_url_before_completion():
    script = (ROOT / "app/static/build-game-url-bonus.js").read_text(encoding="utf-8")

    assert "CHEFE FINAL VENCIDO · ENTREGA PENDENTE" in script
    assert "A missão só será concluída quando uma URL pública real responder com sucesso." in script
    assert "missionDelivered" in script
    assert "MISSÃO CONCLUÍDA" in script
    assert "WATCH_MS = 15000" in script
    assert "/delivery/validate-url" not in script
    assert "method: 'POST'" not in script


def test_delivery_validation_route_is_registered():
    paths = {getattr(route, "path", "") for route in delivery.router.routes}

    assert "/api/projects/{project_id}/delivery/validate-url" in paths


def test_public_url_gate_accepts_only_supported_https_hosts():
    assert _safe_public_url("https://produto.vercel.app") == "https://produto.vercel.app"
    assert _safe_public_url("https://produto.onrender.com/") == "https://produto.onrender.com"
    assert _safe_public_url("http://produto.vercel.app") == ""
    assert _safe_public_url("https://example.com") == ""
    assert _safe_public_url("javascript:alert(1)") == ""


def test_delivery_recovery_never_guesses_repo_named_vercel_domain(monkeypatch):
    project = SimpleNamespace(default_branch="main")
    state = {
        "status": "ready",
        "url": "https://site-pessoal-3.vercel.app",
        "delivery_mode": "external_public_url",
        "providers": {},
    }

    monkeypatch.setattr(
        recovery.delivery,
        "repository_full_name",
        lambda _db, _project: "a-castilho/site-pessoal-3",
    )
    monkeypatch.setattr(recovery, "_github_status_urls", lambda _repo, _branch: [])

    assert recovery._candidate_urls(object(), project, state) == []
    assert recovery._trusted_state_url(object(), project, state) == ""


def test_delivery_recovery_accepts_exact_provider_url(monkeypatch):
    project = SimpleNamespace(default_branch="main")
    provider_url = "https://site-pessoal-3-git-main-acastilho.vercel.app"
    state = {
        "status": "ready",
        "url": provider_url,
        "providers": {"vercel": {"url": provider_url, "deployment_id": "dpl_123"}},
    }

    monkeypatch.setattr(
        recovery.delivery,
        "repository_full_name",
        lambda _db, _project: "a-castilho/site-pessoal-3",
    )
    monkeypatch.setattr(recovery, "_github_status_urls", lambda _repo, _branch: [])

    assert recovery._candidate_urls(object(), project, state) == [provider_url]
    assert recovery._trusted_state_url(object(), project, state) == provider_url


def test_delivery_failure_surfaces_bounded_provider_detail(monkeypatch):
    project = SimpleNamespace(id="project-1")
    state = {
        "status": "failed",
        "last_error": "Não foi possível concluir esta etapa. Tente novamente.",
    }
    saved = {}

    monkeypatch.setattr(
        recovery,
        "_latest_delivery_failure_error",
        lambda _db, _project: "render: HTTP 400",
    )
    monkeypatch.setattr(
        recovery.delivery,
        "save_delivery",
        lambda _db, _project, current: saved.update(current),
    )

    result = recovery._surface_delivery_failure(object(), project, state)

    assert result["last_error"] == "Falha técnica: render: HTTP 400"
    assert saved["last_error"] == "Falha técnica: render: HTTP 400"


def test_failure_detail_is_single_line_and_bounded():
    detail = recovery._safe_failure_detail("render:\nHTTP 400   repositório inválido " + "x" * 300)

    assert "\n" not in detail
    assert len(detail) == 180
    assert detail.startswith("render: HTTP 400 repositório inválido")
