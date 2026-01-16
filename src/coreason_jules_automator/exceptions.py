class AutomatorError(Exception):
    """Base exception for Coreason Jules Automator."""

    pass


class ScmError(AutomatorError):
    """Base exception for SCM (Git/GitHub) related errors."""

    pass


class NetworkError(ScmError):
    """Exception raised for network-related SCM errors (timeouts, connection refused)."""

    pass


class AuthError(ScmError):
    """Exception raised for authentication or permission errors."""

    pass


class StrategyFailure(AutomatorError):
    """Exception raised when a defense strategy fails."""

    pass


class AgentPlatformError(AutomatorError):
    """Exception raised when the Jules agent subprocess fails or crashes."""

    pass
