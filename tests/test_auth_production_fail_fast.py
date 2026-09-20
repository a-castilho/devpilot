from pathlib import Path

import pytest

from app.config import Settings, get_settings


SECURE_AUTH_SECRET = "auth-secret-for-tests-0123456789abcdef"
SECURE_BOOTSTRAP_TOKEN = "bootstrap-token-for-tests-0123456789abcdef"


def settings_for(env: str, **overrides) -> Settings:
    values = {
        "env": env,
        "auth_secret": SECURE_AUTH_SECRET,
        "bootstrap_token": SECURE_BOOTSTRAP_TOKEN,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_local_development_keeps_existing_defaults_compatible():
    settings = settings_for(
        "development",
        auth_secret="",
        bootstrap_token="development-only-token-change-me",
    )

    settings.validate_auth_runtime()
    assert settings.deployed_environment is False


def test_production_rejects_known_default_bootstrap_token():
    settings = settings_for(
        "production",
        bootstrap_token="development-only-token-change-me",
    )

    with pytest.raises(RuntimeError) as error:
        settings.validate_auth_runtime()

    assert "DEVPILOT_BOOTSTRAP_TOKEN" in str(error.value)
    assert "development-only-token-change-me" not in str(error.value)


def test_production_rejects_example_auth_secret_placeholder():
    settings = settings_for(
        "prod",
        auth_secret="change-me-with-a-random-secret-at-least-32-characters",
    )

    with pytest.raises(RuntimeError) as error:
        settings.validate_auth_runtime()

    assert "DEVPILOT_AUTH_SECRET" in str(error.value)
    assert settings.auth_secret not in str(error.value)


def test_deployed_environment_rejects_short_auth_secrets():
    settings = settings_for(
        "homologation",
        auth_secret="too-short",
        bootstrap_token="also-too-short",
    )

    with pytest.raises(RuntimeError) as error:
        settings.validate_auth_runtime()

    message = str(error.value)
    assert "DEVPILOT_AUTH_SECRET" in message
    assert "DEVPILOT_BOOTSTRAP_TOKEN" in message
    assert "too-short" not in message


def test_deployed_environment_accepts_non_placeholder_secrets():
    settings = settings_for("staging")

    settings.validate_auth_runtime()
    assert settings.deployed_environment is True


def test_get_settings_validates_before_preparing_runtime_directories(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    repositories_dir = tmp_path / "repositories"
    host_actions_dir = tmp_path / "host-actions"

    monkeypatch.setenv("DEVPILOT_ENV", "production")
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "too-short")
    monkeypatch.setenv("DEVPILOT_BOOTSTRAP_TOKEN", SECURE_BOOTSTRAP_TOKEN)
    monkeypatch.setenv("DEVPILOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DEVPILOT_REPOSITORIES_DIR", str(repositories_dir))
    monkeypatch.setenv("DEVPILOT_HOST_ACTIONS_DIR", str(host_actions_dir))
    get_settings.cache_clear()

    try:
        with pytest.raises(RuntimeError):
            get_settings()
        assert not data_dir.exists()
        assert not repositories_dir.exists()
        assert not host_actions_dir.exists()
    finally:
        get_settings.cache_clear()
