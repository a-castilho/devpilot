"""RAG bounded context for DEVpilot.

The core DEVpilot depends only on the service contracts exposed by this package.
Infrastructure-specific integrations (pgvector, Redis and embedding providers) must
remain behind adapters so RAG can be disabled without breaking the application.
"""

from .service import RagService, RagSettings

__all__ = ["RagService", "RagSettings"]
