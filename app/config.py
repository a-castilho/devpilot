from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEVPILOT_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite:///./data/devpilot.db"
    data_dir: Path = Path("./data")
    repositories_dir: Path = Path("./data/repositories")
    host_actions_dir: Path = Path("./runtime/host-actions")
    bootstrap_token: str = "development-only-token-change-me"
    auth_secret: str = ""
    auth_token_ttl_seconds: int = 3600
    encryption_key: str = ""
    execution_enabled: bool = False
    embedded_worker: bool = False
    allowed_git_hosts: str = "github.com"
    openai_model: str = "gpt-5.4"
    realtime_model: str = "gpt-realtime-2.1"
    usd_brl_rate: float = 0.0
    linux_agent_url: str = "http://127.0.0.1:8787"
    linux_agent_socket: str = ""
    linux_agent_secret: str = ""
    linux_agent_timeout_seconds: float = 5.0
    managed_trial_clouds_enabled: bool = True
    managed_trial_workspace_slug: str = "default"
    managed_trial_cloud_providers: str = "neon,render,vercel"

    # RAG defaults are deliberately conservative for the 4 GB target host.
    rag_enabled: bool = False
    rag_cache_enabled: bool = True
    rag_git_enabled: bool = True
    rag_docs_enabled: bool = True
    rag_audit_enabled: bool = False
    rag_tasks_enabled: bool = False
    rag_logs_enabled: bool = False
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.70
    rag_cache_ttl_seconds: int = 900
    rag_chunk_size_tokens: int = 500
    rag_chunk_overlap_tokens: int = 50
    rag_index_batch_size: int = 10
    rag_index_worker_concurrency: int = 1
    rag_embedding_dimensions: int = 1536
    redis_url: str = ""

    @property
    def git_hosts(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_git_hosts.split(",") if item.strip()}

    @property
    def managed_trial_providers(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.managed_trial_cloud_providers.split(",")
            if item.strip()
        }

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repositories_dir.mkdir(parents=True, exist_ok=True)
        self.host_actions_dir.mkdir(parents=True, exist_ok=True)
        (self.host_actions_dir / "pending").mkdir(parents=True, exist_ok=True)
        (self.host_actions_dir / "processed").mkdir(parents=True, exist_ok=True)
        (self.host_actions_dir / "failed").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare()
    return settings
