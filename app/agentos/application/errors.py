class ModelUnavailable(RuntimeError):
    """Raised when the configured generative-model adapter cannot serve a request."""


class ExecutionNotFound(LookupError):
    """Raised when an AgentOS goal or execution cannot be resolved."""


class CommandExecutionError(RuntimeError):
    """Raised when a concrete agent command fails or its delegated task fails."""
