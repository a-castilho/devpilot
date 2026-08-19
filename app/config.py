from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVPILOT_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite:///./data/devpilot.db"
    data_dir: Path = Path("./data")
    repositories_dir: Path = Path("./data/repositories")
    bootstrap_token: str = "development-only-token-change-me"
    encryption_key: str = ""
    execution_enabled: bool = False
    allowed_git_hosts: str = "github.com"
    openai_model: str = "gpt-5.4"
    realtime_model: str = "gpt-realtime-2.1"

    # DevPilot task execution. "auto" routes explicit read-only work to local Ollama and
    # keeps repository-writing implementation work on the controlled Codex executor.
    task_executor: str = "auto"
    local_readonly_enabled: bool = True
    local_readonly_max_files: int = 40
    local_readonly_max_file_chars: int = 8_000
    local_readonly_max_context_chars: int = 40_000

    # AgentOS text-generation gateway. Defaults preserve the local Ollama-only behavior.
    # External providers use credentials already encrypted in provider_credentials.
    agentos_model_provider: str = "ollama"
    agentos_model_connection_label: str = ""
    agentos_model_name: str = ""
    agentos_model_fallback: str = ""
    agentos_model_max_output_tokens: int = 1_200

    # Local Ollama remains the lightweight default and optional transient-error fallback.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_enabled: bool = True
    ollama_chat_model: str = "gemma3:1b"
    ollama_embeddings_enabled: bool = True
    ollama_embedding_model: str = "embeddinggemma"
    embedding_fallback_enabled: bool = True
    model_timeout_seconds: float = 60.0

    @property
    def git_hosts(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_git_hosts.split(",") if item.strip()}

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repositories_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare()
    return settings
