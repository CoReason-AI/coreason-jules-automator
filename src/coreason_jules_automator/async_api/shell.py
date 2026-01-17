import asyncio
from typing import AsyncGenerator, List

from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import CommandResult, ShellError


class AsyncShellExecutor:
    """Executes shell commands asynchronously."""

    async def run(self, command: List[str], timeout: int = 300, check: bool = False) -> CommandResult:
        """
        Executes a shell command asynchronously.

        Args:
            command: The command to execute as a list of arguments.
            timeout: Timeout in seconds.
            check: If True, raise ShellError if exit code is non-zero.

        Returns:
            CommandResult containing exit code, stdout, and stderr.
        """
        logger.debug(f"Executing async: {' '.join(command)}")

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
            except asyncio.TimeoutError as e:
                process.kill()
                await process.wait()
                stdout = ""
                stderr = f"Command timed out after {timeout}s"
                result = CommandResult(exit_code=-1, stdout=stdout, stderr=stderr)
                if check:
                    raise ShellError(f"Command timed out: {' '.join(command)}", result) from e
                return result

        except Exception as e:
            result = CommandResult(exit_code=-1, stdout="", stderr=str(e))
            if check:
                raise ShellError(f"Failed to execute command: {e}", result) from e
            return result

        # process.returncode is expected to be int after communicate()
        exit_code = process.returncode if process.returncode is not None else -1
        result = CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

        if check and result.exit_code != 0:
            error_msg = f"Command failed with exit code {result.exit_code}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            elif result.stdout:
                error_msg += f": {result.stdout.strip()}"
            raise ShellError(error_msg, result)

        return result

    async def stream(self, command: List[str], timeout: int = 300) -> AsyncGenerator[str, None]:
        """
        Executes a shell command and yields output line by line.

        Args:
            command: The command to execute.
            timeout: Timeout in seconds for the process to complete after output is consumed.

        Yields:
            Lines of stdout.
        """
        logger.debug(f"Streaming async: {' '.join(command)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            raise ShellError(
                f"Failed to start process: {e}", CommandResult(exit_code=-1, stdout="", stderr=str(e))
            ) from e

        try:
            if process.stdout:
                async for line in process.stdout:
                    yield line.decode()

            await asyncio.wait_for(process.wait(), timeout=timeout)

            if process.returncode != 0:
                stderr_output = await process.stderr.read() if process.stderr else b""
                raise ShellError(
                    f"Command failed with exit code {process.returncode}",
                    CommandResult(exit_code=process.returncode, stdout="", stderr=stderr_output.decode()),
                )

        except asyncio.TimeoutError as e:
            process.kill()
            await process.wait()
            raise ShellError(
                f"Command timed out after {timeout}s", CommandResult(exit_code=-1, stdout="", stderr="Timeout")
            ) from e
        except Exception as e:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if isinstance(e, ShellError):
                raise
            raise ShellError(
                f"Stream execution failed: {e}", CommandResult(exit_code=-1, stdout="", stderr=str(e))
            ) from e
