from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str


class ShellError(RuntimeError):
    """Raised when a shell command fails."""

    def __init__(self, message: str, result: CommandResult):
        super().__init__(message)
        self.result = result
