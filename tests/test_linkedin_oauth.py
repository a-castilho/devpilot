from __future__ import annotations

import pytest

from app.services.linkedin_oauth import (
    LinkedInOAuthError,
    connection_capabilities,
    create_oauth_state,
    hash_binding,
    new_browser_binding,
    new_oauth_nonce,
    verify_oauth_state,
)


def test_oauth_state_round_trip_is_signed():
    nonce = new_oauth_nonce()
    state = create_oauth_state(workspace_id="workspace-1", user_id="user-1", nonce=nonce)
    payload = verify_oauth_state(state)
    assert payload["workspace_id"] == "workspace-1"
    assert payload["user_id"] == "user-1"
    assert payload["nonce"] == nonce


def test_oauth_state_rejects_tampering():
    state = create_oauth_state(workspace_id="workspace-1", user_id="user-1")
    body, signature = state.split(".", 1)
    replacement = "A" if body[-1] != "A" else "B"
    tampered = f"{body[:-1]}{replacement}.{signature}"
    with pytest.raises(LinkedInOAuthError):
        verify_oauth_state(tampered)


def test_browser_binding_is_random_and_hashable():
    first = new_browser_binding()
    second = new_browser_binding()
    assert first != second
    assert hash_binding(first) != first
    assert len(hash_binding(first)) == 64


def test_linkedin_connection_does_not_claim_write_access():
    capabilities = connection_capabilities("openid profile email")
    assert capabilities["oauth_connected"] is True
    assert capabilities["identity_read"] is True
    assert capabilities["profile_write"] is False
    assert "permissões de escrita" in capabilities["profile_write_reason"]
