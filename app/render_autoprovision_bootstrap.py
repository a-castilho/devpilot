from __future__ import annotations

import json
import os
import threading
import time

_STARTED = False


def _is_homologation_runtime() -> bool:
    service_name = os.getenv("RENDER_SERVICE_NAME", "").strip().lower()
    external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().lower()
    env = os.getenv("DEVPILOT_ENV", "").strip().lower()
    return (
        service_name.startswith("devpilot-homolog")
        or "devpilot-homolog" in external_url
        or env in {"homolog", "homologation"}
    )


def _run() -> None:
    time.sleep(8)
    try:
        import httpx
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import ProviderCredential
        from app.services.vault import Vault

        with SessionLocal() as db:
            credentials = list(
                db.scalars(
                    select(ProviderCredential).where(
                        ProviderCredential.provider == "cloud:render",
                        ProviderCredential.label == "cloud-admin",
                        ProviderCredential.enabled.is_(True),
                    )
                ).all()
            )

        if not credentials:
            print("[render-autoprovision] credencial Render ativa não encontrada; nada a fazer", flush=True)
            return

        target = None
        owner_id = ""
        for item in credentials:
            try:
                metadata = json.loads(item.models or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}
            scope = str(metadata.get("scope") or "").strip() if isinstance(metadata, dict) else ""
            if scope:
                target = item
                owner_id = scope
                break

        if target is None:
            print("[render-autoprovision] Workspace / Owner ID não configurado; nada a fazer", flush=True)
            return

        secret = Vault().decrypt(target.encrypted_secret)
        headers = {
            "Authorization": f"Bearer {secret}",
            "Accept": "application/json",
            "User-Agent": "DevPilot-Render-Autoprovision/1.1",
        }

        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            response = client.get(
                "https://api.render.com/v1/services",
                headers=headers,
                params={"ownerId": owner_id, "limit": 100},
            )
            response.raise_for_status()
            data = response.json()
            for wrapper in data if isinstance(data, list) else []:
                if not isinstance(wrapper, dict):
                    continue
                service = wrapper.get("service") if isinstance(wrapper.get("service"), dict) else wrapper
                if str(service.get("name") or "") == "devpilot-homolog-docker":
                    print(f"[render-autoprovision] serviço já existe: {service.get('id', '')}", flush=True)
                    return

            required = {
                "DEVPILOT_DATABASE_URL": os.getenv("DEVPILOT_DATABASE_URL", "").strip(),
                "DEVPILOT_AUTH_SECRET": os.getenv("DEVPILOT_AUTH_SECRET", "").strip(),
                "DEVPILOT_ENCRYPTION_KEY": os.getenv("DEVPILOT_ENCRYPTION_KEY", "").strip(),
            }
            missing = [key for key, value in required.items() if not value]
            if missing:
                print("[render-autoprovision] variáveis obrigatórias ausentes: " + ", ".join(missing), flush=True)
                return

            values = {
                **required,
                "DEVPILOT_ENV": "homologation",
                "DEVPILOT_DATA_DIR": "/tmp/devpilot",
                "DEVPILOT_REPOSITORIES_DIR": "/tmp/devpilot/repositories",
                "DEVPILOT_HOST_ACTIONS_DIR": "/tmp/devpilot/host-actions",
                "DEVPILOT_AUTH_TOKEN_TTL_SECONDS": os.getenv("DEVPILOT_AUTH_TOKEN_TTL_SECONDS", "3600"),
                "DEVPILOT_EXECUTION_ENABLED": "true",
                "DEVPILOT_EMBEDDED_WORKER": "true",
                "DEVPILOT_ALLOWED_GIT_HOSTS": os.getenv("DEVPILOT_ALLOWED_GIT_HOSTS", "github.com"),
            }
            for name in (
                "DEVPILOT_BOOTSTRAP_TOKEN",
                "OPENAI_API_KEY",
                "GOOGLE_API_KEY",
                "GEMINI_API_KEY",
            ):
                value = os.getenv(name, "").strip()
                if value:
                    values[name] = value

            body = {
                "type": "web_service",
                "name": "devpilot-homolog-docker",
                "ownerId": owner_id,
                "repo": "https://github.com/a-castilho/devpilot",
                "branch": "fix/mobile-standard-top-back",
                "autoDeploy": "yes",
                "envVars": [{"key": key, "value": value} for key, value in values.items()],
                "serviceDetails": {
                    "runtime": "docker",
                    "plan": "free",
                    "healthCheckPath": "/health",
                    "envSpecificDetails": {
                        "dockerfilePath": "./Dockerfile",
                        "dockerContext": ".",
                    },
                },
            }
            created = client.post(
                "https://api.render.com/v1/services",
                headers={**headers, "Content-Type": "application/json"},
                json=body,
                timeout=30.0,
            )
            if created.status_code >= 400:
                print(
                    f"[render-autoprovision] criação falhou: HTTP {created.status_code} {created.text[:220]}",
                    flush=True,
                )
                return
            payload = created.json() if created.content else {}
            service = payload.get("service") if isinstance(payload, dict) else None
            if not isinstance(service, dict):
                service = payload if isinstance(payload, dict) else {}
            print(f"[render-autoprovision] serviço criado: {service.get('id', '')}", flush=True)
    except Exception as error:
        print(f"[render-autoprovision] erro: {type(error).__name__}: {error}", flush=True)


def start() -> None:
    global _STARTED
    if _STARTED or not _is_homologation_runtime():
        return
    _STARTED = True
    threading.Thread(target=_run, name="render-autoprovision", daemon=True).start()


start()
