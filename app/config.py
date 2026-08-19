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

    # AgentOS model gateway. The API process stays light and talks to Ollama over HTTP.
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
