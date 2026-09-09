"""DevPilot service layer."""

from app.services.execution_guards import install_execution_guards
from app.services.repair_pipeline import install_repair_pipeline

install_execution_guards()
install_repair_pipeline()
