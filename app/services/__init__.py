"""DevPilot service layer."""

from app.services.github_access_bridge import install_github_access_bridge
from app.services.ai_recovery_bridge import install_ai_last_resort_recovery

install_github_access_bridge()
install_ai_last_resort_recovery()
