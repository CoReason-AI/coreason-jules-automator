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

    async def launch_session(self, task: str) -> Optional[str]:
        self.mission_complete = False
        settings = get_settings()
        logger.info(f"Launching Jules session for repo: {settings.repo_name}...")

        # Construct command
        cmd = [self.executable, "remote", settings.repo_name, "--task", task]

        # Use pexpect-style interaction via the protocol + shell executor?
        # The AsyncShellExecutor runs commands and returns result. It doesn't support interactive streams yet.
        # We need to use asyncio.create_subprocess_exec directly or extend ShellExecutor.
        # For this implementation, we'll use asyncio subprocess directly here for stream handling.

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=None,  # Inherit env
        )

        self.process = process
        self.protocol = JulesProtocol()
        detected_sid: Optional[str] = None

        # Read loop
        # We need to read byte by byte or line by line to feed the protocol
        # but pexpect logic in protocol might expect chunks.
        if not process.stdout:
            logger.error("Failed to capture stdout")
            return None

        # We'll read line by line for simplicity with the protocol's feed method
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace")
                # Feed protocol
                for action in self.protocol.feed(text):
                    if isinstance(action, SignalSessionId):
                        detected_sid = action.sid
                        logger.info(f"✨ Captured SID: {detected_sid}")
                        break
                    elif isinstance(action, SignalComplete):
                        self.mission_complete = True
                        logger.info("✅ Mission Complete signal received.")

                if detected_sid:
                    break

        except Exception as e:
            logger.error(f"Error during launch: {e}")
            if process.returncode is None:
                process.terminate()
            return None

        # If we have SID, we can detach/kill this process as we just wanted to launch it?
        # "jules remote" usually stays running?
        # The 'orchestrator' logic says "Wait for Completion".
        # If we kill it, the remote session might stop?
        # For "teleport" workflow, usually the agent runs until it finishes or pauses.
        # We will keep it running in background or just return SID and let caller handle waiting?
        # The Orchestrator calls `wait_for_completion`.
        # So we probably should detach or keep reference.
        # For this Async version, we might just assume it's running remotely and we can query status?
        # But 'wait_for_completion' in the sync version checked the 'jules' output?
        # Actually, in the sync version, it used `pexpect` to wait.
        # Here we return SID. The `wait_for_completion` method will be called next.
        return detected_sid

    async def wait_for_completion(self, sid: str) -> bool:
        """
        Polls or waits for the session to complete.
        Since we might have detached or it's a remote session, we need a way to check.
        If we kept the process open in `launch_session`, we should continue reading it.
        But `launch_session` returned.
        In a real implementation, we'd probably have a shared state or re-attach.
        For now, let's assume we can attach or just rely on the fact that if we have the process handle,
        we can continue reading.
        """
        # TODO: Robust implementation of re-attaching or continuing the read loop.
        # For the purpose of this refactor step, we'll assume we continue monitoring the process started in
        # launch_session if it's stored in self.process.
        if not hasattr(self, "process") or self.process.returncode is not None:
            # Maybe it finished already?
            return True

        # Continue reading from stdout
        if not self.process.stdout:
            return False

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                for action in self.protocol.feed(text):
                    if isinstance(action, SendStdin):
                        if self.process.stdin:
                            self.process.stdin.write(action.content.encode())
                            await self.process.stdin.drain()
                    elif isinstance(action, SignalComplete):
                        self.mission_complete = True
                        logger.info("✅ Mission Complete signal received.")
                        return True

                # Check if process exited
                if self.process.returncode is not None:
                    break

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
