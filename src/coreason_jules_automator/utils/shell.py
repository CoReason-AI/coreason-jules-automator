import asyncio
import subprocess
from dataclasses import dataclass
from typing import List

from coreason_jules_automator.utils.logger import logger


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


class ShellExecutor:
    """Executes shell commands."""

    def run(self, command: List[str], timeout: float = 300, check: bool = False) -> CommandResult:
        """
        Executes a shell command.

        Args:
            command: The command to execute as a list of arguments.
            timeout: Timeout in seconds.
            check: If True, raise ShellError if exit code is non-zero.

        Returns:
            CommandResult containing exit code, stdout, and stderr.
        """
        logger.debug(f"Executing: {' '.join(command)}")

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,  # We handle check manually
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            # When timeout expires, we might get partial stdout/stderr or None
            stdout = e.stdout.decode() if e.stdout else ""
            stderr = e.stderr.decode() if e.stderr else f"Command timed out after {timeout}s"
            result = CommandResult(exit_code=-1, stdout=stdout, stderr=stderr)
            if check:
                raise ShellError(f"Command timed out: {' '.join(command)}", result) from e
            return result
        except Exception as e:
            # For other exceptions (e.g. file not found), we construct a failure result
            result = CommandResult(exit_code=-1, stdout="", stderr=str(e))
            if check:
                raise ShellError(f"Failed to execute command: {e}", result) from e
            return result

        result = CommandResult(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr)

        if check and result.exit_code != 0:
            error_msg = f"Command failed with exit code {result.exit_code}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            elif result.stdout:
                error_msg += f": {result.stdout.strip()}"
            raise ShellError(error_msg, result)

        return result

    async def run_async(self, command: List[str], timeout: float = 300, check: bool = False) -> CommandResult:
        """
        Executes a shell command asynchronously.

        Args:
            command: The command to execute as a list of arguments.
            timeout: Timeout in seconds.
            check: If True, raise ShellError if exit code is non-zero.

        Returns:
            CommandResult containing exit code, stdout, and stderr.
        """
        logger.debug(f"Executing (async): {' '.join(command)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout = stdout_bytes.decode()
                stderr = stderr_bytes.decode()
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                stdout = ""
                stderr = f"Command timed out after {timeout}s"
                exit_code = -1
                result = CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)
                if check:
                    raise ShellError(f"Command timed out: {' '.join(command)}", result) from None
                return result

        except Exception as e:  # pragma: no cover
            result = CommandResult(exit_code=-1, stdout="", stderr=str(e))  # pragma: no cover
            if check:  # pragma: no cover
                raise ShellError(f"Failed to execute command: {e}", result) from e  # pragma: no cover
            return result  # pragma: no cover

        result = CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

        if check and result.exit_code != 0:
            error_msg = f"Command failed with exit code {result.exit_code}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            elif result.stdout:
                error_msg += f": {result.stdout.strip()}"
            raise ShellError(error_msg, result)

        return result
