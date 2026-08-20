from __future__ import annotations

from pathlib import Path

import httpx

from app.models import Project, Task
from app.services.executor import ensure_repository, git_environment, run
from app.services.organizations import normalize_github_repository


GITHUB_API = "https://api.github.com"


def github_headers(access_token: str) -> dict[str, str]:
    if not access_token:
        raise RuntimeError("GitHub organization credential is required")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }


def create_github_repository(
    organization_login: str,
    access_token: str,
    name: str,
    description: str = "",
    private: bool = True,
) -> dict:
    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": True,
    }
    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers=github_headers(access_token),
    ) as client:
        response = client.post(
            f"{GITHUB_API}/orgs/{organization_login}/repos",
            json=payload,
        )
    if response.status_code in {401, 403}:
        raise RuntimeError("GitHub credential cannot create repositories in this organization")
    if response.status_code == 422:
        message = "GitHub rejected repository creation"
        try:
            body = response.json()
            if body.get("message"):
                message = str(body["message"])
        except ValueError:
            pass
        raise ValueError(message)
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub repository creation failed with HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("GitHub returned an invalid repository response")
    return normalize_github_repository(body)


def _git(path: Path, args: list[str], project: Project):
    return run(args, cwd=path, env_overrides=git_environment(project))


def publish_task_branch(project: Project, task: Task) -> dict:
    path = ensure_repository(project)
    branch = task.branch_name or f"devpilot/{task.id[:8]}"

    verify = _git(path, ["git", "rev-parse", "--verify", branch], project)
    if verify.returncode:
        raise RuntimeError(f"Task branch does not exist locally: {branch}")

    switch = _git(path, ["git", "switch", branch], project)
    if switch.returncode:
        raise RuntimeError(switch.stderr.strip() or "Unable to switch to task branch")

    status = _git(path, ["git", "status", "--porcelain"], project)
    if status.returncode:
        raise RuntimeError(status.stderr.strip() or "Unable to inspect task branch")

    committed_now = False
    if status.stdout.strip():
        add = _git(path, ["git", "add", "-A"], project)
        if add.returncode:
            raise RuntimeError(add.stderr.strip() or "Unable to stage task changes")
        commit = _git(
            path,
            [
                "git",
                "-c",
                "user.name=DevPilot",
                "-c",
                "user.email=devpilot@localhost",
                "commit",
                "-m",
                f"devpilot: {task.title[:120]}",
            ],
            project,
        )
        if commit.returncode:
            raise RuntimeError(commit.stderr.strip() or "Unable to commit task changes")
        committed_now = True

    ahead = _git(
        path,
        ["git", "rev-list", "--count", f"origin/{project.default_branch}..HEAD"],
        project,
    )
    if ahead.returncode:
        raise RuntimeError(ahead.stderr.strip() or "Unable to compare task branch")
    try:
        commits_ahead = int(ahead.stdout.strip() or "0")
    except ValueError as error:
        raise RuntimeError("Git returned an invalid ahead count") from error
    if commits_ahead < 1:
        raise RuntimeError("Task branch has no changes to publish")

    sha_result = _git(path, ["git", "rev-parse", "HEAD"], project)
    if sha_result.returncode:
        raise RuntimeError(sha_result.stderr.strip() or "Unable to resolve task commit")
    commit_sha = sha_result.stdout.strip()

    push = _git(path, ["git", "push", "-u", "origin", branch], project)
    if push.returncode:
        raise RuntimeError(push.stderr.strip() or "Unable to publish task branch")

    return {
        "branch": branch,
        "commit_sha": commit_sha,
        "commits_ahead": commits_ahead,
        "committed_now": committed_now,
    }


def create_or_get_draft_pull_request(
    repository_full_name: str,
    access_token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
) -> dict:
    owner = repository_full_name.split("/", 1)[0]
    headers = github_headers(access_token)
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        existing = client.get(
            f"{GITHUB_API}/repos/{repository_full_name}/pulls",
            params={
                "state": "open",
                "head": f"{owner}:{head_branch}",
                "base": base_branch,
                "per_page": 10,
            },
        )
        if existing.status_code < 400:
            items = existing.json()
            if isinstance(items, list) and items:
                item = items[0]
                return {
                    "number": item["number"],
                    "url": item["html_url"],
                    "draft": bool(item.get("draft", False)),
                    "reused": True,
                }

        response = client.post(
            f"{GITHUB_API}/repos/{repository_full_name}/pulls",
            json={
                "title": title,
                "head": head_branch,
                "base": base_branch,
                "body": body,
                "draft": True,
            },
        )
    if response.status_code in {401, 403}:
        raise RuntimeError("GitHub credential cannot create pull requests")
    if response.status_code == 422:
        raise ValueError("GitHub rejected pull request creation")
    if response.status_code >= 400:
        raise RuntimeError(f"GitHub pull request creation failed with HTTP {response.status_code}")
    item = response.json()
    return {
        "number": item["number"],
        "url": item["html_url"],
        "draft": bool(item.get("draft", True)),
        "reused": False,
    }


def fetch_commit_ci_status(
    repository_full_name: str,
    access_token: str,
    commit_sha: str,
) -> dict:
    headers = github_headers(access_token)
    result = {
        "state": "unknown",
        "statuses": [],
        "checks": [],
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            status_response = client.get(
                f"{GITHUB_API}/repos/{repository_full_name}/commits/{commit_sha}/status"
            )
            checks_response = client.get(
                f"{GITHUB_API}/repos/{repository_full_name}/commits/{commit_sha}/check-runs"
            )
    except httpx.HTTPError as error:
        result["error"] = str(error)
        return result

    if status_response.status_code < 400:
        payload = status_response.json()
        result["statuses"] = [
            {
                "context": item.get("context", ""),
                "state": item.get("state", ""),
                "description": item.get("description", ""),
            }
            for item in payload.get("statuses", [])
        ]
        result["state"] = str(payload.get("state") or "unknown")

    if checks_response.status_code < 400:
        payload = checks_response.json()
        checks = [
            {
                "name": item.get("name", ""),
                "status": item.get("status", ""),
                "conclusion": item.get("conclusion"),
            }
            for item in payload.get("check_runs", [])
        ]
        result["checks"] = checks
        if checks:
            if any(item["status"] != "completed" for item in checks):
                result["state"] = "pending"
            elif any(
                item["conclusion"] not in {"success", "neutral", "skipped"}
                for item in checks
            ):
                result["state"] = "failure"
            else:
                result["state"] = "success"

    return result
