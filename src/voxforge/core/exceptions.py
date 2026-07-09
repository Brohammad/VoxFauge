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


class UnauthorizedError(VoxForgeError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, code="unauthorized")


class ForbiddenError(VoxForgeError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, code="forbidden")


class InvalidCredentialsError(VoxForgeError):
    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message, code="invalid_credentials")


class UserNotFoundError(VoxForgeError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"User not found: {identifier}", code="user_not_found")


class OrganizationNotFoundError(VoxForgeError):
    def __init__(self, org_id: str) -> None:
        super().__init__(f"Organization not found: {org_id}", code="organization_not_found")


class ApiKeyNotFoundError(VoxForgeError):
    def __init__(self, key_id: str) -> None:
        super().__init__(f"API key not found: {key_id}", code="api_key_not_found")


class SamlConnectionNotFoundError(VoxForgeError):
    def __init__(self, connection_id: str) -> None:
        super().__init__(
            f"SAML connection not found: {connection_id}",
            code="saml_connection_not_found",
        )


class SamlAssertionError(VoxForgeError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="saml_assertion_error")
