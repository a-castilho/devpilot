"""DevPilot service layer."""

from app.services.github_access_bridge import install_github_access_bridge
from app.services.ai_recovery_bridge import install_ai_last_resort_recovery

# Credential/checkout recovery is deterministic and runs first. The AI bridge is the
# bounded fallback and may escalate to a human only after automatic recovery is spent.
install_github_access_bridge()
install_ai_last_resort_recovery()
