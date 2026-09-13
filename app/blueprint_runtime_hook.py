from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def install_blueprint_runtime() -> None:
    """Install blueprint materialization around the canonical repository checkout.

    The wrapper is idempotent and fail-open for the optional blueprint layer: repository
    checkout remains authoritative and normal generation continues if a blueprint cannot
    be prepared.
    """
    from app.services import executor as executor_service

    current = executor_service.ensure_repository
    if getattr(current, "__devpilot_blueprint_runtime__", False):
        return

    def ensure_repository_with_blueprint(project):
        path = current(project)
        try:
            from app.blueprint_execution import prepare_blueprint_workspace

            prepare_blueprint_workspace(project, path)
        except (ImportError, KeyError, ValueError, OSError) as error:
            logger.warning("Blueprint preparation failed; continuing with normal generation: %s", error)
        return path

    ensure_repository_with_blueprint.__devpilot_blueprint_runtime__ = True
    executor_service.ensure_repository = ensure_repository_with_blueprint
