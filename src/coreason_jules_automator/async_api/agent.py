import asyncio
from pathlib import Path
from typing import Optional

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.protocols.jules import (
    JulesProtocol,
    SendStdin,
    SignalComplete,
    SignalSessionId,
)
from coreason_jules_automator.utils.logger import logger

from .shell import AsyncShellExecutor


class AsyncJulesAgent:
    """
    Async wrapper for the Jules CLI agent.
    Manages the subprocess, parsing output via JulesProtocol, and sending input.
    """

    def __init__(self, executable: str = "jules", shell: Optional[AsyncShellExecutor] = None):
        self.executable = executable
        self.shell = shell or AsyncShellExecutor()
        self.mission_complete = False
        self.protocol = JulesProtocol()
        # Keep track of process across method calls
        self.process: Optional[asyncio.subprocess.Process] = None

    async def _process_output_stream(self, process: asyncio.subprocess.Process, stop_on_sid: bool = False) -> Optional[str]:
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
            raise e

        return detected_sid

    async def launch_session(self, task: str) -> Optional[str]:
        self.mission_complete = False
        settings = get_settings()
        logger.info(f"Launching Jules session for repo: {settings.repo_name}...")

        # Construct command
        cmd = [self.executable, "remote", settings.repo_name, "--task", task]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=None,  # Inherit env
            )
        except Exception as e:
            logger.error(f"Failed to launch process: {e}")
            return None

        self.process = process

        try:
            detected_sid = await self._process_output_stream(process, stop_on_sid=True)
            return detected_sid

        except Exception as e:
            logger.error(f"Error during launch: {e}")
            await self._cleanup_process(process)
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
