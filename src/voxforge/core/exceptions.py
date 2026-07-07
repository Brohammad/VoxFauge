class VoxForgeError(Exception):
    """Base exception for VoxForge."""

    def __init__(self, message: str, code: str = "internal_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class SessionNotFoundError(VoxForgeError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session not found: {session_id}", code="session_not_found")


class SessionStateError(VoxForgeError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="session_state_error")


class ProviderError(VoxForgeError):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}", code="provider_error")


class PipelineError(VoxForgeError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="pipeline_error")
