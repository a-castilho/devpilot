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
    linkedin_client_id: str = ""
    linkedin_client_secret_ciphertext: str = ""
    linkedin_redirect_uri: str = ""
    linkedin_scopes: str = "openid,profile,email"
    linkedin_oauth_state_ttl_seconds: int = 600

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
