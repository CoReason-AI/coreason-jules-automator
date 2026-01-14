# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import pexpect
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.utils.logger import logger


class JulesAgent:
    """
    Wrapper around the Jules agent that implements the Remote Session + Teleport workflow.
    Includes interactive monitoring to auto-reply to agent queries.
    """

    def __init__(self, executable: str = "jules") -> None:
        self.executable = executable
        self.mission_complete = False

    def _get_active_sids(self) -> Set[str]:
        """Runs `jules remote list --session` and returns active SIDs."""
        try:
            result = subprocess.run(
                [self.executable, "remote", "list", "--session"],
                capture_output=True,
                text=True,
                check=True,
            )
            sids = set()
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    sids.add(parts[0])
            return sids
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list sessions: {e}")
            return set()

    def launch_session(self, task: str) -> Optional[str]:
        """
        Launches a new Jules session and handles interactive prompts.
        """
        settings = get_settings()
        pre_sids = self._get_active_sids()
        self.mission_complete = False
        logger.info(f"Launching Jules session for repo: {settings.repo_name}...")

        # Prepare prompt
        context = ""
        spec_path = Path("SPEC.md")
        if spec_path.exists():
            context = f"Context from SPEC.md:\n{spec_path.read_text(encoding='utf-8')}\n\n"

        full_prompt = context + task

        try:
            # Launch process with pexpect
            child = pexpect.spawn(
                self.executable,
                ["new", "--repo", settings.repo_name],
                encoding="utf-8",
                timeout=300,  # Default timeout for prompt
            )

            # Send initial prompt
            logger.debug("Sending initial task prompt...")
            child.sendline(full_prompt)

            # Monitoring Loop (Wait for SID or Exit)
            start_time = time.time()
            detected_sid = None

            logger.info("Monitoring Jules output for queries...")

            # Regex patterns
            # 0: Question
            # 1: Success Signal
            # 2: EOF
            # 3: TIMEOUT (We use short timeout to check SIDs)
            patterns = [r"\?|\[y/n\]", "100% of the requirements is met", pexpect.EOF, pexpect.TIMEOUT]

            while True:
                # Check for global timeout (30 minutes)
                if time.time() - start_time > 1800:
                    logger.error("❌ Session launch timed out (30m).")
                    break

                # Expect with 5-second timeout to allow polling SIDs
                index = child.expect(patterns, timeout=5)

                if index == 0:  # Question
                    clean_line = child.after.strip() if isinstance(child.after, str) else ""
                    logger.info(f"🤖 Auto-replying to query: {clean_line}")
                    child.sendline("Use your best judgment and make autonomous decisions.")

                elif index == 1:  # Success Signal
                    self.mission_complete = True
                    logger.info("✅ Mission Complete Signal Detected.")

                elif index == 2:  # EOF
                    logger.info("Process finished (EOF).")
                    break

                elif index == 3:  # TIMEOUT
                    # Check for new SIDs
                    post_sids = self._get_active_sids()
                    new_sids = post_sids - pre_sids
                    if new_sids:
                        detected_sid = list(new_sids)[0]
                        logger.info(f"✨ Captured SID: {detected_sid}")
                        break

            # Cleanup
            # If we got the SID, we assume success.
            if detected_sid:
                # We don't kill the process immediately as it might be uploading context
                # We let it run for a bit longer or until it exits
                time.sleep(5)
                if child.isalive():
                    child.terminate(force=True)
                child.close()
                return detected_sid

            logger.error("❌ Failed to detect new session ID.")
            if child.isalive():
                child.terminate(force=True)
            child.close()
            return None

        except Exception as e:
            logger.error(f"Failed to launch Jules: {e}")
            return None

    def wait_for_completion(self, sid: str) -> bool:
        """Monitors the session status until it reaches 'Completed'."""
        logger.info(f"Monitoring status for SID: {sid}")

        # Increased timeout for long campaigns
        timeout_minutes = 30
        start = time.time()

        while (time.time() - start) < (timeout_minutes * 60):
            try:
                result = subprocess.run(
                    [self.executable, "remote", "list", "--session"], capture_output=True, text=True, check=True
                )

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

                # Log heartbeat every minute
                if int(time.time()) % 60 == 0:  # pragma: no cover
                    display_status = " ".join(status_line.split()[4:])
                    logger.info(f"Status heartbeat: {display_status}")

                time.sleep(20)

            except Exception as e:
                logger.error(f"Error monitoring status: {e}")
                time.sleep(10)

        logger.error("❌ Session timed out.")
        return False

    def teleport_and_sync(self, sid: str, target_root: Path) -> bool:
        """Runs teleport in a temp folder and syncs src/ and tests/ to target_root."""
        logger.info(f"📥 Running authoritative teleport for SID {sid}...")

        temp_dir = target_root / f"jules_relay_{sid}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Using input='y\n' to auto-accept any overwrite prompts
            subprocess.run(
                [self.executable, "teleport", sid],
                input="y\n",
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            jules_folders = list(temp_dir.glob("jules-*"))
            if not jules_folders:
                logger.error("❌ Teleport failed: No 'jules-*' folder found.")
                return False

            source_folder = jules_folders[0]
            logger.info(f"🎉 Teleport Success. Syncing from {source_folder.name}...")

            # Sync logic
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

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Teleport command failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
