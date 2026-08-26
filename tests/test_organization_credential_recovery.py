from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_organization_credentials_load_only_after_explicit_navigation():
    loader = (ROOT / "app" / "static" / "feature-loader.js").read_text(encoding="utf-8")

    assert "organizations: ['organization-credentials.js', 'organization-normalization-ui.js']" in loader
    assert "['.nav[data-view=\"organizations\"]', 'organizations']" in loader
    assert "organization-credentials.js" not in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


def test_organization_credential_recovery_keeps_secret_protected_and_revalidates():
    script = (ROOT / "app" / "static" / "organization-credentials.js").read_text(encoding="utf-8")

    assert "type = 'password'" in script
    assert 'type="password"' in script
    assert "autocomplete = 'new-password'" in script
    assert "method: 'PATCH'" in script
    assert "JSON.stringify({access_token: token})" in script
    assert "tokenInput.value = ''" in script
    assert "await syncOrganization(organizationId)" in script
    assert "Resource owner = a-castilho" in script
    assert "MutationObserver" not in script
    assert "createElement('script')" not in script
    assert "console.log" not in script


def test_organization_create_flow_receives_a_protected_token_field_on_demand():
    script = (ROOT / "app" / "static" / "organization-credentials.js").read_text(encoding="utf-8")

    assert "input.name = 'access_token'" in script
    assert "input.spellcheck = false" in script
    assert "vault criptografado" in script
    assert "nunca retorna pela API" in script
