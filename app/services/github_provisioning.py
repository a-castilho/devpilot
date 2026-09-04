from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx

from app.services.organizations import normalize_github_repository


MAX_REPOSITORY_NAME_ATTEMPTS = 20
TRANSIENT_GITHUB_STATUSES = {429, 500, 502, 503, 504}
TRANSIENT_RETRY_DELAYS = (0.35, 0.8, 1.6)


@dataclass(frozen=True)
class GitHubProvisioningError(RuntimeError):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }


def _ensure_token(access_token: str) -> None:
    if not access_token.strip():
        raise GitHubProvisioningError(
            "A organização A Castilho não possui credencial GitHub autorizada para criar repositórios. "
            "Configure um Fine-grained PAT com Resource owner = a-castilho.",
            409,
        )


def _repository_candidate(repository_name: str, attempt: int) -> str:
    if attempt <= 1:
        return repository_name
    suffix = f"-{attempt}"
    return f"{repository_name[:100 - len(suffix)].rstrip('-')}{suffix}"


def _response_payload(response) -> dict:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_messages(response) -> list[str]:
    payload = _response_payload(response)
    messages: list[str] = []
    root_message = payload.get("message")
    if isinstance(root_message, str) and root_message.strip():
        messages.append(root_message.strip())
    errors = payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, str) and item.strip():
                messages.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, str) and message.strip():
                messages.append(message.strip())
    return messages


def _is_repository_name_collision(response) -> bool:
    if response.status_code != 422:
        return False
    payload = _response_payload(response)
    errors = payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or "").strip().lower()
            code = str(item.get("code") or "").strip().lower()
            if field == "name" and code in {"already_exists", "already_taken"}:
                return True
    text = " ".join(_validation_messages(response)).lower()
    collision_markers = (
        "name already exists",
        "already exists on this account",
        "name has already been taken",
        "name is already taken",
        "repository already exists",
    )
    return any(marker in text for marker in collision_markers)


def _validation_detail(response) -> str:
    messages = _validation_messages(response)
    unique: list[str] = []
    for message in messages:
        if message not in unique:
            unique.append(message)
    return " | ".join(unique).strip()[:600]


def _request_with_retry(client: httpx.Client, method: str, url: str, **kwargs):
    """Retry only GitHub transport/server transients; never retry auth/validation failures."""
    last_error: httpx.RequestError | None = None
    response = None
    attempts = len(TRANSIENT_RETRY_DELAYS) + 1
    for attempt in range(attempts):
        try:
            response = client.request(method, url, **kwargs)
            last_error = None
        except httpx.RequestError as error:
            last_error = error
            response = None
        transient_response = response is not None and response.status_code in TRANSIENT_GITHUB_STATUSES
        if not last_error and not transient_response:
            return response
        if attempt < len(TRANSIENT_RETRY_DELAYS):
            time.sleep(TRANSIENT_RETRY_DELAYS[attempt])
    if response is not None:
        return response
    raise GitHubProvisioningError(
        f"GitHub temporariamente indisponível durante {method.upper()} ({last_error}).",
        502,
    ) from last_error


def _translate_starter_error(status_code: int, *, operation: str) -> None:
    if status_code == 401:
        raise GitHubProvisioningError(
            "O token GitHub usado para preparar o starter é inválido ou expirou. "
            "Atualize a credencial da organização a-castilho.",
            401,
        )
    if status_code == 403:
        raise GitHubProvisioningError(
            "O token GitHub consegue acessar a organização, mas não possui permissão para ler/gravar "
            "os arquivos do starter. Edite ou gere um Fine-grained PAT com Resource owner = a-castilho "
            "e Repository permissions > Contents: Read and write. Depois atualize a credencial em "
            "Super Admin > Organizações e tente criar o projeto novamente.",
            403,
        )
    if status_code == 404 and operation == "write":
        raise GitHubProvisioningError(
            "O repositório foi criado, mas o GitHub não encontrou o branch ao gravar o starter. "
            "Atualize a página e tente novamente; se persistir, verifique o branch padrão do repositório.",
            409,
        )
    raise GitHubProvisioningError(
        f"Não foi possível {operation} o starter do produto no GitHub (HTTP {status_code}).",
        502,
    )


def starter_files(project_name: str, description: str = "") -> dict[str, str]:
    safe_name = project_name.strip() or "app"
    safe_description = description.strip() or f"Produto inicial {safe_name}"
    backend = f'''from __future__ import annotations

import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title={safe_name!r})


def database_status() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return "not_configured"
    try:
        with psycopg.connect(database_url, connect_timeout=4) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return "ok"
    except Exception:
        return "unavailable"


@app.get("/health")
def health():
    database = database_status()
    if os.getenv("DATABASE_URL") and database != "ok":
        raise HTTPException(
            status_code=503,
            detail={{"status": "degraded", "database": database}},
        )
    return {{
        "status": "ok",
        "service": {safe_name!r},
        "environment": os.getenv("APP_ENV", "development"),
        "database": database,
    }}


@app.get("/api/status")
def api_status():
    return health()
'''
    frontend = f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{safe_name}</title>
  <style>
    body{{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#e6edf3;margin:0;display:grid;min-height:100vh;place-items:center}}
    main{{width:min(680px,calc(100vw - 40px));border:1px solid #30363d;border-radius:18px;padding:28px;background:#161b22}}
    h1{{margin-top:0}} .ok{{color:#7ee787}} .error{{color:#ff7b72}}
  </style>
</head>
<body>
<main>
  <small>PRODUTO · DEVPILOT</small>
  <h1>{safe_name}</h1>
  <p>{safe_description}</p>
  <p id="status">Validando frontend → backend → banco…</p>
  <pre id="payload"></pre>
</main>
<script>
(async()=>{{
  const status=document.querySelector('#status');
  const payload=document.querySelector('#payload');
  try{{
    const response=await fetch('/api/status',{{headers:{{'Accept':'application/json'}}}});
    const data=await response.json();
    if(!response.ok)throw new Error(JSON.stringify(data));
    status.className='ok';
    status.textContent='Produto online';
    payload.textContent=JSON.stringify(data,null,2);
  }}catch(error){{
    status.className='error';
    status.textContent='Produto ainda está sendo preparado';
    payload.textContent=String(error);
  }}
}})();
</script>
</body>
</html>
'''
    vercel = '''{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "routes": [
    {"src": "/api/(.*)", "dest": "${APP_BACKEND_URL}/api/$1"},
    {"src": "/health", "dest": "${APP_BACKEND_URL}/health"},
    {"handle": "filesystem"},
    {"src": "/.*", "dest": "/index.html"}
  ]
}
'''
    return {
        ".devpilot-product.json": '{"managed_by":"devpilot","purpose":"client-product","version":1}\n',
        "backend/main.py": backend,
        "requirements.txt": "fastapi>=0.116,<1\nuvicorn[standard]>=0.35,<1\npsycopg[binary]>=3.2,<4\n",
        "Dockerfile": (
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY backend ./backend\n"
            'CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]\n'
        ),
        "index.html": frontend,
        "vercel.json": vercel,
        ".gitignore": "__pycache__/\n*.py[cod]\n.env\n.venv/\n",
    }


def _degraded_starter_result(
    *,
    branch: str,
    created: list[str],
    existing: list[str],
    status_code: int,
    operation: str,
    path: str,
) -> dict:
    return {
        "status": "degraded",
        "branch": branch,
        "created": created,
        "existing": existing,
        "pending": [path],
        "error": f"Starter pendente: falha temporária ao {operation} {path} no GitHub (HTTP {status_code}).",
    }


def bootstrap_repository(
    organization_login: str,
    repository_name: str,
    access_token: str,
    *,
    project_name: str,
    description: str = "",
    branch: str = "main",
) -> dict:
    """Best-effort starter bootstrap.

    A confirmed DevPilot repository is usable by the execution pipeline even when
    GitHub's Contents API is temporarily returning 5xx/429. In that case we keep
    the repository linked and report the starter as degraded instead of losing
    repository_url and entering an endless reprovision loop.
    """
    _ensure_token(access_token)
    created: list[str] = []
    existing: list[str] = []
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=_headers(access_token)) as client:
        for path, content in starter_files(project_name, description).items():
            url = f"https://api.github.com/repos/{organization_login}/{repository_name}/contents/{path}"
            check = _request_with_retry(client, "GET", url, params={"ref": branch})
            if check.status_code == 200:
                existing.append(path)
                continue
            if check.status_code in TRANSIENT_GITHUB_STATUSES:
                return _degraded_starter_result(
                    branch=branch,
                    created=created,
                    existing=existing,
                    status_code=check.status_code,
                    operation="verificar",
                    path=path,
                )
            if check.status_code != 404:
                _translate_starter_error(check.status_code, operation="verificar")
            response = _request_with_retry(
                client,
                "PUT",
                url,
                json={
                    "message": f"chore: preparar produto inicial ({path})",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": branch,
                },
            )
            if response.status_code in TRANSIENT_GITHUB_STATUSES:
                return _degraded_starter_result(
                    branch=branch,
                    created=created,
                    existing=existing,
                    status_code=response.status_code,
                    operation="gravar",
                    path=path,
                )
            if response.status_code not in {200, 201}:
                _translate_starter_error(response.status_code, operation="gravar")
            created.append(path)
    return {
        "status": "ready",
        "branch": branch,
        "created": created,
        "existing": existing,
        "pending": [],
        "error": "",
    }


def _resume_managed_repository(
    organization_login: str,
    repository_name: str,
    access_token: str,
) -> dict | None:
    """Adopt only a repository whose DevPilot marker can be positively confirmed."""
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=_headers(access_token)) as client:
        repo_response = _request_with_retry(
            client, "GET", f"https://api.github.com/repos/{organization_login}/{repository_name}"
        )
        if repo_response.status_code == 404:
            return None
        if repo_response.status_code in TRANSIENT_GITHUB_STATUSES:
            raise GitHubProvisioningError(
                f"GitHub temporariamente indisponível ao localizar o repositório (HTTP {repo_response.status_code}).",
                502,
            )
        if repo_response.status_code != 200:
            _translate_creation_error(repo_response)
            return None
        marker_response = _request_with_retry(
            client,
            "GET",
            f"https://api.github.com/repos/{organization_login}/{repository_name}/contents/.devpilot-product.json",
        )
    if marker_response.status_code == 404:
        return None
    if marker_response.status_code in TRANSIENT_GITHUB_STATUSES:
        raise GitHubProvisioningError(
            f"GitHub temporariamente indisponível ao confirmar o marcador DevPilot (HTTP {marker_response.status_code}).",
            502,
        )
    if marker_response.status_code != 200:
        return None
    try:
        return normalize_github_repository(repo_response.json())
    except (KeyError, TypeError, ValueError) as error:
        raise GitHubProvisioningError(
            "GitHub retornou uma resposta inválida ao retomar o repositório."
        ) from error


def _translate_creation_error(response) -> None:
    if response.status_code == 401:
        raise GitHubProvisioningError("O token GitHub é inválido ou expirou.", 401)
    if response.status_code == 403:
        raise GitHubProvisioningError(
            "A credencial GitHub não autoriza criar repositórios em a-castilho. "
            "Use um Fine-grained PAT com Resource owner = a-castilho e Repository permissions > "
            "Administration: Read and write e Contents: Read and write.",
            403,
        )
    if response.status_code == 404:
        raise GitHubProvisioningError(
            "A organização A Castilho não foi encontrada ou não está acessível pela credencial configurada.",
            404,
        )
    if response.status_code == 422:
        if _is_repository_name_collision(response):
            return
        detail = _validation_detail(response)
        detail_text = f" Detalhe: {detail}." if detail else ""
        raise GitHubProvisioningError(
            "O GitHub recusou a criação do repositório por uma regra de validação da organização "
            f"a-castilho.{detail_text} Verifique políticas de criação de repositórios, propriedades "
            "obrigatórias e permissões da credencial GitHub.",
            422,
        )
    if response.status_code >= 400:
        raise GitHubProvisioningError(
            f"Falha ao criar repositório no GitHub (HTTP {response.status_code}).", 502
        )


def _remote_with_starter(remote: dict, starter: dict) -> dict:
    result = dict(remote)
    result["starter_provision_state"] = str(starter.get("status") or "ready")
    result["starter_provision_error"] = str(starter.get("error") or "")
    result["starter_pending"] = list(starter.get("pending") or [])
    return result


def create_github_repository(
    organization_login: str,
    repository_name: str,
    description: str,
    access_token: str,
) -> dict:
    """Create or adopt a private DevPilot repository without losing it on transient starter failures."""
    _ensure_token(access_token)

    for attempt in range(1, MAX_REPOSITORY_NAME_ATTEMPTS + 1):
        candidate = _repository_candidate(repository_name, attempt)
        payload = {
            "name": candidate,
            "description": description,
            "private": True,
            "auto_init": True,
        }
        with httpx.Client(timeout=30.0, follow_redirects=True, headers=_headers(access_token)) as client:
            response = _request_with_retry(
                client,
                "POST",
                f"https://api.github.com/orgs/{organization_login}/repos",
                json=payload,
            )

        _translate_creation_error(response)

        if response.status_code == 422:
            resumed = _resume_managed_repository(organization_login, candidate, access_token)
            if resumed:
                starter = bootstrap_repository(
                    organization_login,
                    candidate,
                    access_token,
                    project_name=repository_name,
                    description=description,
                    branch=resumed["default_branch"],
                )
                return _remote_with_starter(resumed, starter)
            continue

        try:
            remote = normalize_github_repository(response.json())
        except (KeyError, TypeError, ValueError) as error:
            raise GitHubProvisioningError(
                "GitHub retornou uma resposta inválida ao criar o repositório."
            ) from error

        starter = bootstrap_repository(
            organization_login,
            candidate,
            access_token,
            project_name=repository_name,
            description=description,
            branch=remote["default_branch"],
        )
        return _remote_with_starter(remote, starter)

    raise GitHubProvisioningError(
        "Não foi possível reservar um nome de repositório para o projeto.",
        409,
    )
