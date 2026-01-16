class JulesAutomatorError(Exception):
    """Base exception for Coreason Jules Automator."""
    pass

class AgentProcessError(JulesAutomatorError):
    """Raised when the Jules Agent subprocess fails or encounters an error."""
    pass

class StrategyVerificationError(JulesAutomatorError):
    """Raised when a defense strategy fails verification (and it's an error, not just a failed check)."""
    pass

class GitOperationError(JulesAutomatorError):
    """Raised when a git operation fails."""
    pass
