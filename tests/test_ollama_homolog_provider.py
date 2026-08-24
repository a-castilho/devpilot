from __future__ import annotations

from pathlib import Path

from app.linux_agent import ollama_runtime
from app.ollama_provider_routes import _normalize_models


def test_normalize_ollama_models_deduplicates_and_strips():
    assert _normalize_models([" tinyllama ", "tinyllama", "phi3:mini", ""]) == [
        "tinyllama",
        "phi3:mini",
    ]


def test_ensure_ollama_reuses_running_instance(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(ollama_runtime, "_tags", lambda timeout=2.0: ["tinyllama"])

    result = ollama_runtime.ensure_ollama(tmp_path)

    assert result["status"] == "running"
    assert result["started"] is False
    assert result["models"] == ["tinyllama"]


def test_ensure_ollama_starts_with_fixed_argument_array(monkeypatch, tmp_path: Path):
    calls = {"tags": 0}
    popen = {}

    def fake_tags(timeout=2.0):
        calls["tags"] += 1
        if calls["tags"] == 1:
            raise ollama_runtime.OllamaRuntimeError("offline")
        return ["tinyllama"]

    class FakeProcess:
        pass

    def fake_popen(args, **kwargs):
        popen["args"] = args
        popen["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(ollama_runtime, "_tags", fake_tags)
    monkeypatch.setattr(ollama_runtime.shutil, "which", lambda name: "/usr/local/bin/ollama")
    monkeypatch.setattr(ollama_runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ollama_runtime.time, "sleep", lambda seconds: None)

    result = ollama_runtime.ensure_ollama(tmp_path, startup_timeout=1.0)

    assert result["started"] is True
    assert popen["args"] == ["/usr/local/bin/ollama", "serve"]
    assert popen["kwargs"]["env"]["OLLAMA_HOST"] == "0.0.0.0:11434"
    assert popen["kwargs"]["start_new_session"] is True
