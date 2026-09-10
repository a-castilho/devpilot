"""DevPilot service layer."""

from app.services import executor as executor
from app.services.github_credential_bridge import install as install_github_credential_bridge

install_github_credential_bridge(executor)
