from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from app.services.organizations import normalize_github_repository


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


def create_github_repository(
    organization_login: str,
    repository_name: str,
    description: str,
    access_token: str,
) -> dict:
    """Create a private initialized repository inside an authorized GitHub organization."""
    _ensure_token(access_token)

    payload = {
        "name": repository_name,
        "description": description,
        "private": True,
        "auto_init": True,
    }

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers=_headers(access_token),
    ) as client:
        response = client.post(
            f"https://api.github.com/orgs/{organization_login}/repos",
            json=payload,
        )

    if response.status_code == 401:
        raise GitHubProvisioningError(
            "O token GitHub é inválido ou expirou. Gere um novo Fine-grained PAT com "
            "Resource owner = a-castilho.",
            401,
        )
    if response.status_code == 403:
        raise GitHubProvisioningError(
            "A credencial GitHub não autoriza criar repositórios em a-castilho. Use um Fine-grained PAT "
            "com Resource owner = a-castilho e Repository permissions > Administration: Read and write. "
            "Confirme também que a organização permite criação de repositórios e aprovou o token, se exigido.",
            403,
        )
    if response.status_code == 404:
        raise GitHubProvisioningError(
            "A organização A Castilho não foi encontrada ou não está acessível pela credencial configurada. "
            "Confira se o Resource owner do Fine-grained PAT é a-castilho.",
            404,
        )
    if response.status_code == 422:
        detail = ""
        try:
            data = response.json()
            detail = str(data.get("message") or "").strip()
        except (TypeError, ValueError):
            pass
        message = "Não foi possível criar o repositório no GitHub. O nome pode já estar em uso."
        if detail:
            message = f"{message} GitHub: {detail}"
        raise GitHubProvisioningError(message, 409)
    if response.status_code >= 400:
        raise GitHubProvisioningError(
            f"Falha ao criar repositório no GitHub (HTTP {response.status_code}).",
            502,
        )

    try:
        data = response.json()
        return normalize_github_repository(data)
    except (KeyError, TypeError, ValueError) as error:
        raise GitHubProvisioningError("GitHub retornou uma resposta inválida ao criar o repositório.") from error


def homologation_starter_files(project_name: str, description: str = "") -> dict[str, str]:
    """Return a small deployable starter used only to make first homologation testable."""
    safe_name = project_name.strip() or "app"
    safe_description = description.strip() or f"Homologação inicial de {safe_name}"

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
  <title>{safe_name} · Homologação</title>
  <style>
    body{{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#e6edf3;margin:0;display:grid;min-height:100vh;place-items:center}}
    main{{width:min(680px,calc(100vw - 40px));border:1px solid #30363d;border-radius:18px;padding:28px;background:#161b22}}
    h1{{margin-top:0}} code{{color:#7ee787}} .ok{{color:#7ee787}} .error{{color:#ff7b72}}
  </style>
</head>
<body>
<main>
  <small>DEVPILOT · HOMOLOGAÇÃO</small>
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
    status.textContent='Homologação pronta';
    payload.textContent=JSON.stringify(data,null,2);
  }}catch(error){{
    status.className='error';
    status.textContent='Homologação ainda não está pronta';
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
    {
      "src": "/api/(.*)",
      "dest": "${APP_BACKEND_URL}/api/$1",
      "env": ["APP_BACKEND_URL"]
    },
    {
      "src": "/health",
      "dest": "${APP_BACKEND_URL}/health",
      "env": ["APP_BACKEND_URL"]
    },
    {
      "handle": "filesystem"
    },
    {
      "src": "/.*",
      "dest": "/index.html"
    }
  ]
}
'''

    return {
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


def bootstrap_github_repository(
    organization_login: str,
    repository_name: str,
    access_token: str,
    *,
    project_name: str,
    description: str = "",
    branch: str = "main",
) -> dict:
    """Seed a newly created repository with a minimal Render + Vercel homologation starter.

    Existing files are kept intact, which makes the operation resumable after partial failures.
    """
    _ensure_token(access_token)
    files = homologation_starter_files(project_name, description)
    created: list[str] = []
    existing: list[str] = []

    with httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers=_headers(access_token),
    ) as client:
        for path, content in files.items():
            url = f"https://api.github.com/repos/{organization_login}/{repository_name}/contents/{path}"
            check = client.get(url, params={"ref": branch})
            if check.status_code == 200:
                existing.append(path)
                continue
            if check.status_code not in {404}:
                raise GitHubProvisioningError(
                    f"Não foi possível verificar o starter de homologação no GitHub (HTTP {check.status_code})."
                )

            response = client.put(
                url,
                json={
                    "message": f"chore: preparar homologação inicial ({path})",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": branch,
                },
            )
            if response.status_code not in {200, 201}:
                raise GitHubProvisioningError(
                    f"Não foi possível criar o starter de homologação no GitHub (HTTP {response.status_code})."
                )
            created.append(path)

    return {
        "status": "ready",
        "branch": branch,
        "created": created,
        "existing": existing,
    }
