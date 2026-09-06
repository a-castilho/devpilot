from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing", "ci"})
_INSECURE_AUTH_PLACEHOLDERS = frozenset(
    {
        "development-only-token-change-me",
        "change-me-with-at-least-32-characters",
        "change-me-with-a-random-secret-at-least-32-characters",
    }
)
_MIN_AUTH_SECRET_LENGTH = 32


def _insecure_auth_secret(value: str) -> bool:
    normalized = value.strip()
    return (
        len(normalized) < _MIN_AUTH_SECRET_LENGTH
        or normalized.casefold() in _INSECURE_AUTH_PLACEHOLDERS
    )


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
    linkedin_client_id: str = ""
    linkedin_client_secret_ciphertext: str = ""
    linkedin_redirect_uri: str = ""
    linkedin_scopes: str = "openid,profile,email"
    linkedin_oauth_state_ttl_seconds: int = 600

    # RAG defaults are deliberately conservative for the 4 GB target host.
    # When empty, RAG storage follows database_url for backward compatibility.
    rag_database_url: str = ""
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
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_base_url: str = "https://api.openai.com/v1"
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

    @property
    def linkedin_scope_set(self) -> set[str]:
        return {
            item.strip()
            for item in self.linkedin_scopes.replace(" ", ",").split(",")
            if item.strip()
        }

    @property
    def deployed_environment(self) -> bool:
        return self.env.strip().lower() not in _LOCAL_ENVIRONMENTS

    def validate_auth_runtime(self) -> None:
        """Reject predictable authentication secrets before a deployed process starts."""
        if not self.deployed_environment:
            return

        invalid: list[str] = []
        if _insecure_auth_secret(self.auth_secret):
            invalid.append("DEVPILOT_AUTH_SECRET")
        if _insecure_auth_secret(self.bootstrap_token):
            invalid.append("DEVPILOT_BOOTSTRAP_TOKEN")
        if invalid:
            names = ", ".join(invalid)
            raise RuntimeError(
                "Configuração de autenticação insegura para ambiente não local. "
                f"Defina segredos aleatórios com pelo menos {_MIN_AUTH_SECRET_LENGTH} caracteres: {names}"
            )

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
    settings.validate_auth_runtime()
    settings.prepare()
    return settings
