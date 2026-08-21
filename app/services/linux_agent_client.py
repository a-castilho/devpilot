from __future__ import annotations

import json
import secrets
import time
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.linux_agent.auth import sign_request


class LinuxAgentError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class LinuxAgentClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.linux_agent_url.rstrip("/")
        self.socket_path = settings.linux_agent_socket.strip()
        self.secret = settings.linux_agent_secret.strip()
        self.timeout = settings.linux_agent_timeout_seconds

    def _client(self) -> httpx.Client:
        if self.socket_path:
            transport = httpx.HTTPTransport(uds=self.socket_path)
            return httpx.Client(
                base_url="http://devpilot-linux-agent",
                transport=transport,
                timeout=self.timeout,
            )
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def health(self) -> dict:
        try:
            with self._client() as client:
                response = client.get("/health")
            return response.json()
        except (httpx.HTTPError, ValueError, OSError) as error:
            raise LinuxAgentError("Linux Agent não está acessível", status_code=503) from error

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
    ) -> dict:
        if len(self.secret) < 32:
            raise LinuxAgentError(
                "DEVPILOT_LINUX_AGENT_SECRET não configurado no DevPilot",
                status_code=503,
            )

        body = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else b""
        )
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(20)
        parsed = urlsplit(path)
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        signature = sign_request(
            self.secret,
            timestamp=timestamp,
            nonce=nonce,
            method=method,
            target=target,
            body=body,
        )
        headers = {
            "X-DevPilot-Timestamp": timestamp,
            "X-DevPilot-Nonce": nonce,
            "X-DevPilot-Signature": signature,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"

        try:
            with self._client() as client:
                response = client.request(
                    method,
                    path,
                    headers=headers,
                    content=body,
                )
        except httpx.TimeoutException as error:
            raise LinuxAgentError("Linux Agent não respondeu dentro do limite", status_code=504) from error
        except (httpx.HTTPError, OSError) as error:
            raise LinuxAgentError("Falha de conexão com o Linux Agent", status_code=503) from error

        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        if response.is_error:
            detail = data.get("detail") if isinstance(data, dict) else None
            raise LinuxAgentError(
                str(detail or f"Linux Agent retornou HTTP {response.status_code}"),
                status_code=response.status_code,
            )
        return data
