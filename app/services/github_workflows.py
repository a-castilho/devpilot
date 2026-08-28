from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx


_GITHUB_HOSTS = {"github.com", "www.github.com"}


def repository_full_name(repository_url: str) -> str:
    value = str(repository_url or "").strip()
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1]
    else:
        parsed = urlparse(value)
        if parsed.hostname not in _GITHUB_HOSTS:
            raise ValueError("Only GitHub repositories support workflow correlation")
        path = parsed.path
    normalized = re.sub(r"\.git$", "", path.strip("/"))
    parts = normalized.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Invalid GitHub repository URL")
    return f"{parts[0]}/{parts[1]}"


def _headers(access_token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _github_error(response: httpx.Response) -> RuntimeError:
    if response.status_code == 401:
        return RuntimeError("GitHub credential is invalid or expired")
    if response.status_code == 403:
        return RuntimeError("GitHub credential does not have permission to read Actions")
    if response.status_code == 404:
        return RuntimeError("GitHub repository or Actions workflow is not visible to this credential")
    return RuntimeError(f"GitHub Actions query failed with HTTP {response.status_code}")


def fetch_workflow_evidence(
    repository_url: str,
    commit_sha: str,
    access_token: str | None = None,
) -> dict[str, object]:
    sha = str(commit_sha or "").strip()
    if not sha:
        return {"correlated": False, "reason": "missing_commit_sha", "workflow": None, "jobs": []}

    full_name = repository_full_name(repository_url)
    headers = _headers(access_token)
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        runs_response = client.get(
            f"https://api.github.com/repos/{full_name}/actions/runs",
            params={"head_sha": sha, "per_page": 20},
        )
        if runs_response.status_code >= 400:
            raise _github_error(runs_response)
        payload = runs_response.json()
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError("GitHub returned an invalid workflow-runs response")
        exact = [item for item in runs if str(item.get("head_sha") or "") == sha]
        if not exact:
            return {
                "correlated": False,
                "reason": "workflow_not_found_for_commit",
                "repository": full_name,
                "commit_sha": sha,
                "workflow": None,
                "jobs": [],
            }

        exact.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        selected = exact[0]
        run_id = int(selected["id"])
        jobs_response = client.get(
            f"https://api.github.com/repos/{full_name}/actions/runs/{run_id}/jobs",
            params={"per_page": 100},
        )
        if jobs_response.status_code >= 400:
            raise _github_error(jobs_response)
        jobs_payload = jobs_response.json()
        jobs = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else None
        if not isinstance(jobs, list):
            raise RuntimeError("GitHub returned an invalid workflow-jobs response")

    workflow = {
        "id": run_id,
        "name": str(selected.get("name") or "workflow"),
        "status": str(selected.get("status") or "unknown"),
        "conclusion": selected.get("conclusion"),
        "event": str(selected.get("event") or ""),
        "run_number": selected.get("run_number"),
        "html_url": str(selected.get("html_url") or ""),
        "created_at": selected.get("created_at"),
        "updated_at": selected.get("updated_at"),
    }
    normalized_jobs = [
        {
            "id": item.get("id"),
            "name": str(item.get("name") or "job"),
            "status": str(item.get("status") or "unknown"),
            "conclusion": item.get("conclusion"),
            "html_url": str(item.get("html_url") or ""),
            "started_at": item.get("started_at"),
            "completed_at": item.get("completed_at"),
        }
        for item in jobs
    ]
    return {
        "correlated": True,
        "reason": "exact_commit_sha",
        "repository": full_name,
        "commit_sha": sha,
        "workflow": workflow,
        "jobs": normalized_jobs,
    }
