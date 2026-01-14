import asyncio
import shutil
from pathlib import Path
from typing import Optional

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.protocols.jules import JulesProtocol, SendStdin, SignalComplete, SignalSessionId
from coreason_jules_automator.utils.logger import logger

from .shell import AsyncShellExecutor


class AsyncJulesAgent:
    def __init__(self, executable: str = "jules", shell: Optional[AsyncShellExecutor] = None):
        self.executable = executable
        self.shell = shell or AsyncShellExecutor()

    async def launch_session(self, task: str) -> Optional[str]:
        settings = get_settings()
        logger.info(f"Launching Jules session for repo: {settings.repo_name}...")

        # Prepare prompt
        context = ""
        spec_path = Path("SPEC.md")
        if spec_path.exists():
            context = f"Context from SPEC.md:\n{spec_path.read_text(encoding='utf-8')}\n\n"

        full_prompt = context + task

        protocol = JulesProtocol()
        detected_sid = None

        # Start process
        try:
            process = await asyncio.create_subprocess_exec(
                self.executable,
                "new",
                "--repo",
                settings.repo_name,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr to stdout for parsing
            )
        except Exception as e:
            logger.error(f"Failed to start Jules process: {e}")
            return None

        # Send initial prompt
        if process.stdin:
            try:
                process.stdin.write(full_prompt.encode())
                process.stdin.write(b"\n")
                await process.stdin.drain()
            except Exception as e:
                logger.error(f"Failed to write to stdin: {e}")

        try:
            start_time = asyncio.get_running_loop().time()
            timeout_seconds = 1800  # 30 mins

            while True:
                if asyncio.get_running_loop().time() - start_time > timeout_seconds:
                    logger.error("❌ Session launch timed out.")
                    break

                try:
                    if process.stdout:
                        chunk_bytes = await asyncio.wait_for(process.stdout.read(1024), timeout=5.0)
                    else:
                        break
                except asyncio.TimeoutError:
                    continue

                if not chunk_bytes:
                    logger.info("Process finished (EOF).")
                    break

                chunk = chunk_bytes.decode(errors="replace")
                # Feed to protocol
                for action in protocol.process_output(chunk):
                    if isinstance(action, SendStdin):
                        logger.info(f"🤖 Auto-replying: {action.text.strip()}")
                        if process.stdin:
                            process.stdin.write(action.text.encode())
                            await process.stdin.drain()
                    elif isinstance(action, SignalSessionId):
                        detected_sid = action.sid
                        logger.info(f"✨ Captured SID: {detected_sid}")
                        break
                    elif isinstance(action, SignalComplete):
                        logger.info("✅ Mission Complete Signal Detected.")
                        pass

                if detected_sid:
                    break

            # Cleanup
            await asyncio.sleep(5)
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()

            return detected_sid

        except Exception as e:
            logger.error(f"Failed to launch Jules: {e}")
            if process.returncode is None:
                process.kill()
            return None

    async def wait_for_completion(self, sid: str) -> bool:
        logger.info(f"Monitoring status for SID: {sid}")
        timeout_minutes = 30
        start = asyncio.get_running_loop().time()

        while (asyncio.get_running_loop().time() - start) < (timeout_minutes * 60):
            try:
                result = await self.shell.run([self.executable, "remote", "list", "--session"], check=True)

                status_line = ""
                for line in result.stdout.splitlines():
                    if line.strip().startswith(sid):
                        status_line = line
                        break

                if not status_line:
                    logger.warning(f"SID {sid} disappeared from list.")
                    return False

                if "completed" in status_line.lower():
                    logger.info("✅ Final Signal Detected (Completed).")
                    return True

                if "failed" in status_line.lower() or "error" in status_line.lower():
                    logger.error(f"❌ Session failed: {status_line}")
                    return False

                await asyncio.sleep(20)

            except Exception as e:
                logger.error(f"Error monitoring status: {e}")
                await asyncio.sleep(10)

        logger.error("❌ Session timed out.")
        return False

    async def teleport_and_sync(self, sid: str, target_root: Path) -> bool:
        logger.info(f"📥 Running authoritative teleport for SID {sid}...")

        temp_dir = target_root / f"jules_relay_{sid}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            process = await asyncio.create_subprocess_exec(
                self.executable,
                "teleport",
                sid,
                cwd=str(temp_dir),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr_bytes = await process.communicate(input=b"y\n")
            stderr = stderr_bytes.decode()

            if process.returncode != 0:
                logger.error(f"Teleport command failed: {stderr}")
                return False

            # Sync logic in thread to avoid blocking
            def _sync_files():
                jules_folders = list(temp_dir.glob("jules-*"))
                if not jules_folders:
                    return False, "No 'jules-*' folder found."

                source_folder = jules_folders[0]
                logger.info(f"🎉 Teleport Success. Syncing from {source_folder.name}...")

                dirs_to_sync = ["src", "tests"]
                files_to_sync = ["requirements.txt", "pyproject.toml"]

                for d in dirs_to_sync:
                    src_path = source_folder / d
                    dst_path = target_root / d
                    if src_path.exists():
                        if dst_path.exists():
                            shutil.rmtree(dst_path)
                        shutil.copytree(src_path, dst_path)

                for f in files_to_sync:
                    src_file = source_folder / f
                    dst_file = target_root / f
                    if src_file.exists():
                        shutil.copy2(src_file, dst_file)
                return True, ""

            success, msg = await asyncio.to_thread(_sync_files)
            if not success:
                logger.error(f"❌ Teleport failed: {msg}")
                return False

            return True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
        finally:
            if temp_dir.exists():
                await asyncio.to_thread(shutil.rmtree, temp_dir)
