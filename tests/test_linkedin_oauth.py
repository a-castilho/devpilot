from __future__ import annotations

import pytest

from app.services.linkedin_oauth import (
    LinkedInOAuthError,
    connection_capabilities,
    create_oauth_state,
    verify_oauth_state,
)


def test_oauth_state_round_trip_is_signed():
    state = create_oauth_state(workspace_id="workspace-1", user_id="user-1")
    payload = verify_oauth_state(state)
    assert payload["workspace_id"] == "workspace-1"
    assert payload["user_id"] == "user-1"
    assert payload["nonce"]


def test_oauth_state_rejects_tampering():
    state = create_oauth_state(workspace_id="workspace-1", user_id="user-1")
    body, signature = state.split(".", 1)
    tampered = f"{body[:-1]}A.{signature}"
    with pytest.raises(LinkedInOAuthError):
        verify_oauth_state(tampered)


def test_linkedin_connection_does_not_claim_write_access():
    capabilities = connection_capabilities("openid profile email")
    assert capabilities["oauth_connected"] is True
    assert capabilities["identity_read"] is True
    assert capabilities["profile_write"] is False
    assert "permissões de escrita" in capabilities["profile_write_reason"]
