class SandboxError(Exception):
    """Base exception for all sandebox SDK errors."""

    pass


class SandboxAuthError(SandboxError):
    """Raised on authentication failures."""

    pass


class SandboxNotFoundError(SandboxError):
    """Raised when the requested sandbox or resource is not found."""

    pass


class SandboxConnectionError(SandboxError):
    """Raised when connecting to the sandebox server fails."""

    pass
