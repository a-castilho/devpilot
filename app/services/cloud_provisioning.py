from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


NEON_API = "https://console.neon.tech/api/v2"
RENDER_API = "https://api.render.com/v1"
VERCEL_API = "https://api.vercel.com"


class CloudProvisioningError(RuntimeError):
    def __init__(self, provider: str, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


@dataclass(frozen=True)
class CloudConnection:
    token: str
    account_id: str = ""


@dataclass(frozen=True)
class NeonProvision:
    public: dict[str, Any]
    database_url: str


def selected_cloud_providers(blueprint: dict[str, Any] | None) -> list[str]:
    """Infer the managed cloud resources needed by a project blueprint."""
    data = blueprint if isinstance(blueprint, dict) else {}
    databases = {str(value) for value in data.get("databases", []) if value}
    backend = {str(value) for value in data.get("backend", []) if value}
    frontend = {str(value) for value in data.get("frontend", []) if value}

    selected: list[str] = []
    if "postgresql" in databases:
        selected.append("neon")
    if not backend or any(value != "none" for value in backend):
        selected.append("render")
    if not frontend or any(value != "none" for value in frontend):
        selected.append("vercel")
    return selected


def _safe_error(provider: str, error: Exception) -> str:
    if isinstance(error, CloudProvisioningError):
        return str(error)[:500]
    return f"Falha ao provisionar {provider}."[:500]


class CloudProvisioner:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "CloudProvisioner":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(
        self,
        provider: str,
        method: str,
        url: str,
        connection: CloudConnection,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {connection.token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                json=json,
                params=params,
            )
        except httpx.HTTPError as error:
            raise CloudProvisioningError(provider, f"{provider}: API indisponível") from error

        if response.status_code >= 400:
            # Provider payloads can echo request data. Persist only status/provider,
            # never a raw response that could contain credentials or environment values.
            raise CloudProvisioningError(
                provider,
                f"{provider}: API retornou HTTP {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise CloudProvisioningError(provider, f"{provider}: resposta inválida da API") from error

    def provision_neon(
        self,
        *,
        connection: CloudConnection,
        project_name: str,
    ) -> NeonProvision:
        project_body: dict[str, Any] = {
            "name": project_name,
            "pg_version": 18,
            "branch": {
                "name": "main",
                "role_name": "app",
                "database_name": "app",
            },
        }
        if connection.account_id:
            project_body["org_id"] = connection.account_id

        created = self._request(
            "neon",
            "POST",
            f"{NEON_API}/projects",
            connection,
            json={"project": project_body},
        )
        if not isinstance(created, dict):
            raise CloudProvisioningError("neon", "neon: projeto não retornado")

        project = created.get("project") or {}
        branch = created.get("branch") or {}
        databases = created.get("databases") or []
        roles = created.get("roles") or []

        project_id = str(project.get("id") or "")
        main_branch_id = str(branch.get("id") or "")
        if not project_id or not main_branch_id:
            raise CloudProvisioningError("neon", "neon: IDs do projeto não retornados")

        database_name = "app"
        if databases and isinstance(databases[0], dict):
            database_name = str(databases[0].get("name") or database_name)
        role_name = "app"
        if roles and isinstance(roles[0], dict):
            role_name = str(roles[0].get("name") or role_name)

        homolog_created = self._request(
            "neon",
            "POST",
            f"{NEON_API}/projects/{project_id}/branches",
            connection,
            json={
                "branch": {
                    "name": "homolog",
                    "parent_id": main_branch_id,
                },
                "endpoints": [{"type": "read_write"}],
            },
        )
        homolog_branch = {}
        if isinstance(homolog_created, dict):
            homolog_branch = homolog_created.get("branch") or {}
        homolog_branch_id = str(homolog_branch.get("id") or "")
        if not homolog_branch_id:
            raise CloudProvisioningError("neon", "neon: branch de homologação não retornada")

        database_url = self._connection_uri(
            connection=connection,
            project_id=project_id,
            branch_id=homolog_branch_id,
            database_name=database_name,
            role_name=role_name,
        )

        return NeonProvision(
            public={
                "status": "ready",
                "project_id": project_id,
                "main_branch_id": main_branch_id,
                "homolog_branch_id": homolog_branch_id,
                "database_name": database_name,
                "role_name": role_name,
                "region_id": str(project.get("region_id") or ""),
            },
            database_url=database_url,
        )

    def _connection_uri(
        self,
        *,
        connection: CloudConnection,
        project_id: str,
        branch_id: str,
        database_name: str,
        role_name: str,
    ) -> str:
        payload = self._request(
            "neon",
            "GET",
            f"{NEON_API}/projects/{project_id}/connection_uri",
            connection,
            params={
                "branch_id": branch_id,
                "database_name": database_name,
                "role_name": role_name,
                "pooled": "true",
            },
        )
        if not isinstance(payload, dict):
            raise CloudProvisioningError("neon", "neon: connection URI não retornada")
        uri = str(payload.get("uri") or "")
        if not uri:
            raise CloudProvisioningError("neon", "neon: connection URI vazia")
        return uri

    def neon_database_url(
        self,
        *,
        connection: CloudConnection,
        metadata: dict[str, Any],
    ) -> str:
        return self._connection_uri(
            connection=connection,
            project_id=str(metadata.get("project_id") or ""),
            branch_id=str(metadata.get("homolog_branch_id") or ""),
            database_name=str(metadata.get("database_name") or "app"),
            role_name=str(metadata.get("role_name") or "app"),
        )

    def provision_render(
        self,
        *,
        connection: CloudConnection,
        project_name: str,
        repository_url: str,
        branch: str,
        database_url: str | None,
    ) -> dict[str, Any]:
        if not connection.account_id:
            raise CloudProvisioningError(
                "render",
                "render: owner/account ID não configurado",
                status_code=409,
            )

        created_project = self._request(
            "render",
            "POST",
            f"{RENDER_API}/projects",
            connection,
            json={
                "name": project_name,
                "ownerId": connection.account_id,
                "environments": [
                    {"name": "homolog"},
                    {"name": "production"},
                ],
            },
        )
        project_id = ""
        if isinstance(created_project, dict):
            project_id = str(
                created_project.get("id")
                or (created_project.get("project") or {}).get("id")
                or ""
            )
        if not project_id:
            raise CloudProvisioningError("render", "render: projeto não retornado")

        environments_payload = self._request(
            "render",
            "GET",
            f"{RENDER_API}/environments",
            connection,
            params={"projectId": project_id},
        )
        environment_rows = environments_payload
        if isinstance(environments_payload, dict):
            environment_rows = (
                environments_payload.get("environments")
                or environments_payload.get("items")
                or []
            )
        homolog_environment_id = ""
        production_environment_id = ""
        if isinstance(environment_rows, list):
            for row in environment_rows:
                if not isinstance(row, dict):
                    continue
                environment = row.get("environment") if isinstance(row.get("environment"), dict) else row
                name = str(environment.get("name") or "").lower()
                env_id = str(environment.get("id") or "")
                if name == "homolog":
                    homolog_environment_id = env_id
                elif name == "production":
                    production_environment_id = env_id

        env_vars = [{"key": "APP_ENV", "value": "homolog"}]
        if database_url:
            env_vars.append({"key": "DATABASE_URL", "value": database_url})

        service_body: dict[str, Any] = {
            "type": "web_service",
            "name": f"{project_name}-homolog",
            "ownerId": connection.account_id,
            "repo": repository_url,
            "branch": branch,
            "autoDeploy": "yes",
            "envVars": env_vars,
            "serviceDetails": {
                "runtime": "docker",
                "plan": "free",
                "healthCheckPath": "/health",
                "envSpecificDetails": {
                    "dockerfilePath": "./Dockerfile",
                },
            },
        }
        if homolog_environment_id:
            service_body["environmentId"] = homolog_environment_id

        created_service = self._request(
            "render",
            "POST",
            f"{RENDER_API}/services",
            connection,
            json=service_body,
        )
        service = created_service
        if isinstance(created_service, dict) and isinstance(created_service.get("service"), dict):
            service = created_service["service"]
        if not isinstance(service, dict):
            raise CloudProvisioningError("render", "render: serviço não retornado")

        service_id = str(service.get("id") or "")
        if not service_id:
            raise CloudProvisioningError("render", "render: ID do serviço não retornado")

        return {
            "status": "provisioned",
            "project_id": project_id,
            "homolog_environment_id": homolog_environment_id,
            "production_environment_id": production_environment_id,
            "service_id": service_id,
            "url": str(service.get("serviceDetails", {}).get("url") or service.get("url") or ""),
        }

    def provision_vercel(
        self,
        *,
        connection: CloudConnection,
        project_name: str,
        repository_full_name: str,
        backend_url: str | None,
    ) -> dict[str, Any]:
        params = {"teamId": connection.account_id} if connection.account_id else None
        created = self._request(
            "vercel",
            "POST",
            f"{VERCEL_API}/v11/projects",
            connection,
            params=params,
            json={
                "name": project_name,
                "gitRepository": {
                    "type": "github",
                    "repo": repository_full_name,
                },
            },
        )
        if not isinstance(created, dict):
            raise CloudProvisioningError("vercel", "vercel: projeto não retornado")
        project_id = str(created.get("id") or "")
        if not project_id:
            raise CloudProvisioningError("vercel", "vercel: ID do projeto não retornado")

        if backend_url:
            env_url = f"{VERCEL_API}/v10/projects/{project_id}/env"
            env_params: dict[str, Any] = {"upsert": "true"}
            if connection.account_id:
                env_params["teamId"] = connection.account_id
            self._request(
                "vercel",
                "POST",
                env_url,
                connection,
                params=env_params,
                json=[
                    {
                        "key": key,
                        "value": backend_url,
                        "type": "encrypted",
                        "target": ["production", "preview"],
                    }
                    for key in ("APP_BACKEND_URL", "NEXT_PUBLIC_API_URL", "VITE_API_URL")
                ],
            )

        return {
            "status": "provisioned",
            "project_id": project_id,
            "project_name": str(created.get("name") or project_name),
            "team_id": connection.account_id,
        }


def provision_cloud_stack(
    *,
    project_name: str,
    repository_url: str,
    repository_full_name: str,
    branch: str,
    blueprint: dict[str, Any] | None,
    connections: dict[str, CloudConnection],
    existing: dict[str, Any] | None = None,
    provisioner: CloudProvisioner | None = None,
) -> dict[str, Any]:
    requested = selected_cloud_providers(blueprint)
    previous = existing if isinstance(existing, dict) else {}
    previous_providers = previous.get("providers")
    providers: dict[str, dict[str, Any]] = (
        {key: dict(value) for key, value in previous_providers.items() if isinstance(value, dict)}
        if isinstance(previous_providers, dict)
        else {}
    )
    errors: dict[str, str] = {}
    missing = [provider for provider in requested if provider not in connections]

    worker = provisioner or CloudProvisioner()
    owns_worker = provisioner is None
    try:
        database_url: str | None = None

        if "neon" in requested and "neon" in connections:
            current = providers.get("neon") or {}
            try:
                if current.get("status") == "ready":
                    database_url = worker.neon_database_url(
                        connection=connections["neon"],
                        metadata=current,
                    )
                else:
                    neon = worker.provision_neon(
                        connection=connections["neon"],
                        project_name=project_name,
                    )
                    providers["neon"] = neon.public
                    database_url = neon.database_url
            except Exception as error:  # provider boundary
                errors["neon"] = _safe_error("neon", error)

        if "render" in requested and "render" in connections:
            current = providers.get("render") or {}
            if current.get("status") != "provisioned":
                try:
                    providers["render"] = worker.provision_render(
                        connection=connections["render"],
                        project_name=project_name,
                        repository_url=repository_url,
                        branch=branch,
                        database_url=database_url,
                    )
                except Exception as error:  # provider boundary
                    errors["render"] = _safe_error("render", error)

        backend_url = None
        render_state = providers.get("render") or {}
        if render_state.get("status") == "provisioned":
            backend_url = str(render_state.get("url") or "") or None

        if "vercel" in requested and "vercel" in connections:
            current = providers.get("vercel") or {}
            if current.get("status") != "provisioned":
                try:
                    providers["vercel"] = worker.provision_vercel(
                        connection=connections["vercel"],
                        project_name=project_name,
                        repository_full_name=repository_full_name,
                        backend_url=backend_url,
                    )
                except Exception as error:  # provider boundary
                    errors["vercel"] = _safe_error("vercel", error)
    finally:
        if owns_worker:
            worker.close()

    completed = {
        name
        for name in requested
        if (providers.get(name) or {}).get("status") in {"ready", "provisioned"}
    }
    if not requested:
        status = "not_requested"
    elif len(completed) == len(requested):
        status = "provisioned"
    elif completed:
        status = "partial"
    elif missing and len(missing) == len(requested):
        status = "blocked"
    elif errors:
        status = "failed"
    else:
        status = "pending"

    return {
        "requested": requested,
        "status": status,
        "providers": {name: providers[name] for name in requested if name in providers},
        "missing_credentials": missing,
        "errors": errors,
    }
