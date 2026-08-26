#!/usr/bin/env python3
"""Create one DevPilot task for a failed GitHub Actions run.

The bridge is intentionally limited to ingestion and local remediation. It never
publishes Git changes or integrates main; those actions remain behind DevPilot's
existing approval policy.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def request_json(base_url: str, token: str, method: str, path: str, payload=None):
    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "devpilot-ci-failure-bridge/1",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def normalized_repo(value: str) -> str:
    raw = value.strip().rstrip("/")
    if raw.startswith("git@github.com:"):
        raw = "https://github.com/" + raw.split(":", 1)[1]
    parsed = urlparse(raw)
    if parsed.hostname and parsed.hostname.lower() == "github.com":
        path = parsed.path.strip("/")
    else:
        path = raw.removeprefix("github.com/").strip("/")
    return path.removesuffix(".git").lower()


def find_project(projects: list[dict], repository: str) -> dict | None:
    expected = normalized_repo(repository)
    for project in projects:
        if normalized_repo(str(project.get("repository_url") or "")) == expected:
            return project
    return None


def main() -> int:
    try:
        base_url = required_env("DEVPILOT_AUTOMATION_URL")
        token = required_env("DEVPILOT_AUTOMATION_TOKEN")
        repository = required_env("GITHUB_REPOSITORY")
        run_id = required_env("DEVPILOT_CI_RUN_ID")
        run_url = required_env("DEVPILOT_CI_RUN_URL")
        head_sha = required_env("DEVPILOT_CI_HEAD_SHA")

        projects = request_json(base_url, token, "GET", "/api/projects")
        project = find_project(projects, repository)
        if not project:
            raise RuntimeError(f"DevPilot project not found for repository {repository}")

        marker = f"[github-ci-run:{run_id}]"
        query = urlencode({"project_id": project["id"], "limit": 100})
        tasks = request_json(base_url, token, "GET", f"/api/tasks?{query}")
        if any(marker in str(task.get("prompt") or "") for task in tasks):
            print(f"CI failure already registered: run {run_id}")
            return 0

        prompt = (
            f"{marker}\n"
            "Uma execução do CI oficial falhou. Recupere o estado atual do repositório, "
            "identifique a etapa que falhou, diagnostique a causa raiz, aplique somente a "
            "correção local necessária e execute bash scripts/test-all.sh. Preserve os gates "
            "existentes e deixe a alteração pronta para revisão. Não publique alterações e "
            "não integre a branch main automaticamente.\n\n"
            f"Repositório: {repository}\n"
            f"Run: {run_url}\n"
            f"Commit: {head_sha}\n"
        )
        payload = {
            "project_id": project["id"],
            "title": f"Corrigir falha do CI #{run_id}",
            "prompt": prompt,
            "source": "api",
            "priority": 90,
            "requires_approval": False,
        }
        task = request_json(base_url, token, "POST", "/api/tasks", payload)
        print(f"DevPilot task created: {task.get('id', 'unknown')} for CI run {run_id}")
        return 0
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        print(f"CI failure bridge error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
