from types import SimpleNamespace

from app.services import executor, github_access_bridge


def test_cloud_admin_github_credentials_are_repository_credential_sources():
    assert github_access_bridge.GITHUB_CREDENTIAL_PROVIDERS == (
        "github",
        "cloud:github",
        "cloud-github",
    )


def test_legacy_cloud_admin_payload_extracts_github_token(monkeypatch):
    credential = SimpleNamespace(encrypted_secret="encrypted")
    vault = SimpleNamespace(
        decrypt=lambda _value: '{"token":"github-system-token","account_id":"a-castilho"}'
    )
    monkeypatch.setattr(github_access_bridge, "Vault", lambda: vault)

    assert github_access_bridge._credential_token(credential) == "github-system-token"


def test_bridge_routes_every_executor_checkout_through_authenticated_preflight():
    github_access_bridge.install_github_access_bridge()

    assert getattr(executor.ensure_repository, "_devpilot_authenticated_checkout", False) is True
