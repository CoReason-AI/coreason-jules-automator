import asyncio
from pathlib import Path
from typing import Optional, Type
from types import TracebackType

from coreason_jules_automator.config import get_settings, Settings
from coreason_jules_automator.protocols.jules import (
    JulesProtocol,
    SendStdin,
    SignalComplete,
    SignalSessionId,
)
from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.exceptions import AgentProcessError

from .shell import AsyncShellExecutor


class AsyncJulesAgent:
    """
    Async wrapper for the Jules CLI agent.
    Manages the subprocess, parsing output via JulesProtocol, and sending input.
    Implements Async Context Manager for resource safety.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        executable: str = "jules",
        shell: Optional[AsyncShellExecutor] = None,
    ):
        self.settings = settings or get_settings()
        self.executable = executable
        self.shell = shell or AsyncShellExecutor()
        self.mission_complete = False
        self.protocol = JulesProtocol()
        # Keep track of process across method calls
        self.process: Optional[asyncio.subprocess.Process] = None

    async def __aenter__(self) -> "AsyncJulesAgent":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.process:
            logger.info("Cleaning up Jules agent process...")
            await self._cleanup_process(self.process)
            self.process = None

    async def _process_output_stream(
        self, process: asyncio.subprocess.Process, stop_on_sid: bool = False
    ) -> Optional[str]:
        """
        Reads stdout line by line, feeds protocol, handles auto-replies.

        Args:
            process: The subprocess to monitor.
            stop_on_sid: If True, returns immediately when SID is detected.

        Returns:
            The detected SID if found, else None.
        """
        if not process.stdout:
            logger.error("Process has no stdout")
            return None

        detected_sid = None
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace")

                for action in self.protocol.process_output(text):
                    if isinstance(action, SendStdin):
                        logger.info(f"Action SendStdin: {action.text}")
                        if process.stdin:
                            process.stdin.write(action.text.encode())
                            await process.stdin.drain()

                    elif isinstance(action, SignalSessionId):
                        detected_sid = action.sid
                        logger.info(f"✨ Captured SID: {detected_sid}")

                    elif isinstance(action, SignalComplete):
                        self.mission_complete = True
                        logger.info("✅ Mission Complete signal received.")

                # Stop conditions
                if stop_on_sid and detected_sid:
                    return detected_sid

                if not stop_on_sid and self.mission_complete:
                    return detected_sid

        except Exception as e:
            logger.error(f"Error processing stream: {e}")
            raise AgentProcessError(f"Error processing stream: {e}") from e

        return detected_sid

    async def launch(self, task: str) -> str:
        """
        Launches the Jules session.
        Returns:
            The Session ID (SID).
        Raises:
            AgentProcessError: If launch fails or SID not found.
        """
        self.mission_complete = False
        repo_name = self.settings.repo_name
        logger.info(f"Launching Jules session for repo: {repo_name}...")

        # Construct command
        cmd = [self.executable, "remote", repo_name, "--task", task]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=None,  # Inherit env
            )
        except Exception as e:
            raise AgentProcessError(f"Failed to launch process: {e}") from e

        self.process = process

        try:
            detected_sid = await self._process_output_stream(process, stop_on_sid=True)
            if not detected_sid:
                raise AgentProcessError("Failed to obtain Session ID (SID). Process might have exited early.")
            return detected_sid

        except Exception as e:
            logger.error(f"Error during launch: {e}")
            # If we are in context manager, __aexit__ will handle cleanup, but if we fail here,
            # we might want to ensure cleanup immediately if the exception bubbles up?
            # Actually, standard practice is that if __aenter__ succeeds, __aexit__ is called.
            # But launch is called inside the with block. So exception here will trigger __aexit__.
            raise e

    # Keep legacy name for compatibility if needed, or just redirect
    async def launch_session(self, task: str) -> Optional[str]:
        try:
            return await self.launch(task)
        except AgentProcessError:
            return None

    async def wait_for_completion(self, sid: str) -> bool:
        """
        Polls or waits for the session to complete.
        """
        # If process is not running or we don't have handle, check flag
        if not self.process or self.process.returncode is not None:
            return self.mission_complete

        try:
            await self._process_output_stream(self.process, stop_on_sid=False)
        except Exception as e:
            logger.error(f"Error during wait: {e}")
            return False

        return self.mission_complete

    async def teleport_and_sync(self, sid: str, target_dir: Path) -> bool:
        """
        Runs `jules teleport` to sync code.
        """
        cmd = [self.executable, "teleport", sid, str(target_dir)]
        try:
            result = await self.shell.run(cmd, check=True)
            logger.info(f"Teleport result: {result.stdout}")
            return True
        except Exception as e:
            logger.error(f"Teleport failed: {e}")
            return False

    async def _cleanup_process(self, process: asyncio.subprocess.Process) -> None:
        """
        Helper to cleanly terminate a subprocess.
        """
        if process.returncode is not None:
            return

        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
