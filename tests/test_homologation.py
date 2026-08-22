from __future__ import annotations

import json

import httpx

from app.services.cloud_provisioning import CloudConnection
from app.services.homologation import (
    trigger_vercel_homologation,
    verify_homologation,
)


def test_trigger_vercel_homologation_creates_preview_from_github():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = dict(request.url.params)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "dpl_homolog",
                "url": "produto-preview.vercel.app",
                "status": "QUEUED",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = trigger_vercel_homologation(
        connection=CloudConnection("secret-vercel", "team-1"),
        project_id="prj-1",
        project_name="produto",
        repository_full_name="a-castilho/produto",
        branch="main",
        client=client,
    )

    assert seen["method"] == "POST"
    assert seen["path"] == "/v13/deployments"
    assert seen["query"]["teamId"] == "team-1"
    assert seen["query"]["skipAutoDetectionConfirmation"] == "1"
    assert seen["body"]["project"] == "prj-1"
    assert seen["body"]["gitSource"] == {
        "type": "github",
        "org": "a-castilho",
        "repo": "produto",
        "ref": "main",
    }
    assert result["deployment_id"] == "dpl_homolog"
    assert result["environment"] == "preview"
    assert result["url"] == "https://produto-preview.vercel.app"
    assert "secret-vercel" not in json.dumps(result)


def test_verify_homologation_checks_render_frontend_and_proxy():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url) in {
            "https://produto-homolog.onrender.com/health",
            "https://produto-preview.vercel.app/",
            "https://produto-preview.vercel.app/health",
        }:
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404)

    cloud = {
        "providers": {
            "render": {
                "status": "provisioned",
                "url": "https://produto-homolog.onrender.com",
            },
            "vercel": {
                "status": "provisioned",
                "homologation": {
                    "deployment_id": "dpl-1",
                    "url": "https://produto-preview.vercel.app",
                },
            },
        }
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = verify_homologation(cloud, client=client)

    assert result["status"] == "ready"
    assert result["url"] == "https://produto-preview.vercel.app"
    assert [check["name"] for check in result["checks"]] == [
        "render_health",
        "vercel_frontend",
        "vercel_backend_proxy",
    ]
    assert all(check["ok"] for check in result["checks"])


def test_verify_homologation_stays_pending_while_deployment_is_starting():
    def handler(request: httpx.Request) -> httpx.Response:
        if "onrender.com" in request.url.host:
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(503)

    cloud = {
        "providers": {
            "render": {
                "status": "provisioned",
                "url": "https://produto-homolog.onrender.com",
            },
            "vercel": {
                "status": "provisioned",
                "homologation": {
                    "deployment_id": "dpl-1",
                    "url": "https://produto-preview.vercel.app",
                },
            },
        }
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = verify_homologation(cloud, client=client)

    assert result["status"] == "pending"
    failed = [check["name"] for check in result["checks"] if not check["ok"]]
    assert failed == ["vercel_frontend", "vercel_backend_proxy"]
