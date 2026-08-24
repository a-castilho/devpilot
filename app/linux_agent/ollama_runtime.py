from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class OllamaRuntimeError(RuntimeError):
    pass


def _api_base_url() -> str:
    return os.environ.get("DEVPILOT_OLLAMA_LOCAL_URL", "http://127.0.0.1:11434").rstrip("/")


def _listen_address() -> str:
    # Homologation can override this when the Ollama API must also be reachable
    # from a container on the same Linux host. The default stays loopback-only;
    # DevPilot talks to Ollama through the signed Linux Agent proxy.
    return os.environ.get("DEVPILOT_OLLAMA_LISTEN", "127.0.0.1:11434").strip()


def _tags(timeout: float = 2.0) -> list[str]:
    request = urllib.request.Request(
        f"{_api_base_url()}/api/tags",
        headers={"Accept": "application/json", "User-Agent": "DevPilot-Linux-Agent/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise OllamaRuntimeError("Ollama não respondeu no Linux de homologação") from error

    result: list[str] = []
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        model = str(item.get("model") or item.get("name") or "").strip()
        if model and model not in result:
            result.append(model)
    return result


def _log_path(data_dir: Path) -> Path:
    path = Path(data_dir).expanduser().resolve() / "ollama"
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path / "ollama.log"


def ensure_ollama(data_dir: Path, *, startup_timeout: float = 10.0) -> dict[str, Any]:
    """Ensure one Ollama server process is reachable on the homologation Linux host."""
    try:
        models = _tags()
        return {
            "status": "running",
            "started": False,
            "models": models,
            "api_url": _api_base_url(),
        }
    except OllamaRuntimeError:
        pass

    executable = shutil.which("ollama")
    if not executable:
        raise OllamaRuntimeError(
            "Ollama não está instalado no Linux de homologação. Instale o binário antes de cadastrar o provedor."
        )

    env = os.environ.copy()
    env["OLLAMA_HOST"] = _listen_address()
    log_path = _log_path(data_dir)
    log_handle = log_path.open("ab", buffering=0)
    try:
        subprocess.Popen(
            [executable, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(Path.home()),
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        log_handle.close()
        raise OllamaRuntimeError("Não foi possível iniciar o Ollama no Linux de homologação") from error
    finally:
        if not log_handle.closed:
            log_handle.close()

    deadline = time.monotonic() + max(1.0, startup_timeout)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        time.sleep(0.4)
        try:
            models = _tags()
            return {
                "status": "running",
                "started": True,
                "models": models,
                "api_url": _api_base_url(),
            }
        except OllamaRuntimeError as error:
            last_error = error

    raise OllamaRuntimeError("Ollama foi iniciado, mas a API não ficou disponível a tempo") from last_error


def chat_ollama(
    *,
    model: str,
    instructions: str,
    input_text: str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    installed = _tags(timeout=3.0)
    if model not in installed:
        raise OllamaRuntimeError(f"Modelo Ollama não instalado: {model}")

    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "options": {"num_predict": 280},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{_api_base_url()}/api/chat",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "DevPilot-Linux-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise OllamaRuntimeError("Ollama falhou ao gerar a resposta no Linux de homologação") from error

    message = payload.get("message") or {}
    answer = str(message.get("content") or payload.get("response") or "").strip()
    if not answer:
        raise OllamaRuntimeError("Ollama retornou uma resposta vazia")
    return {
        "answer": answer,
        "model": model,
        "input_tokens": int(payload.get("prompt_eval_count") or 0),
        "output_tokens": int(payload.get("eval_count") or 0),
    }
