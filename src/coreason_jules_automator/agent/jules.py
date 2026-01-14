# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Set
import pexpect

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.utils.logger import logger


class JulesAgent:
    """
    Wrapper around the Jules agent that implements the Remote Session + Teleport workflow.
    """

    def __init__(self, executable: str = "jules") -> None:
        self.executable = executable
        self.mission_complete = False

    def _get_active_sids(self) -> Set[str]:
        """
        Runs `jules remote list --session` and returns a set of active numeric SIDs.
        """
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
        Launches a new Jules session in bootstrap mode and captures the new SID.
        Uses pexpect to handle interactive prompts and auto-replies.
        """
        self.mission_complete = False
        settings = get_settings()

        # 1. Snapshot existing sessions
        pre_sids = self._get_active_sids()
        logger.info(f"Launching Jules session for repo: {settings.repo_name}...")

        # 2. Prepare prompt input
        context = ""
        spec_path = Path("SPEC.md")
        if spec_path.exists():
            context = f"Context from SPEC.md:\n{spec_path.read_text(encoding='utf-8')}\n\n"

        full_prompt = context + task

        # 3. Durable Launch with pexpect
        try:
            cmd = f"{self.executable} new --repo {settings.repo_name}"
            # encoding='utf-8' is crucial for string matching
            child = pexpect.spawn(cmd, encoding="utf-8", timeout=1800)

            # Send prompt immediately
            child.sendline(full_prompt)

            logger.info("Jules process launched. Entering interaction loop...")

            # Regex patterns
            patterns = [
                r"\?|\[y/n\]",                      # 0: Question
                r"100% of the requirements is met", # 1: Success
                r"SID:\s*(\d+)",                    # 2: SID detection (if printed)
                pexpect.EOF,                        # 3: End of process
                pexpect.TIMEOUT                     # 4: Timeout (internal poll interval)
            ]

            detected_sid: Optional[str] = None
            start_time = time.time()

            # Loop for up to 30 minutes
            while (time.time() - start_time) < 1800:
                # Use a short timeout for expect to allow periodic polling of SIDs
                index = child.expect(patterns, timeout=5)

                if index == 0: # Question
                    logger.info("Detected prompt. Auto-replying...")
                    child.sendline("Use your best judgment and make autonomous decisions.")

                elif index == 1: # Success
                    logger.info("✅ Mission Complete Signal Detected.")
                    self.mission_complete = True
                    # If we found SID, we might continue until EOF or return?
                    # We should probably continue to handle any final output or cleanup
                    # but if we have SID, we can technically return.
                    # However, sticking to the loop allows the process to finish cleanly if it wants to exit.

                elif index == 2: # SID Pattern
                    if child.match:
                        sid_str = child.match.group(1)
                        logger.info(f"✨ Captured SID from output: {sid_str}")
                        detected_sid = sid_str

                elif index == 3: # EOF
                    logger.info("Jules process finished (EOF).")
                    break

                elif index == 4: # TIMEOUT (5s)
                    # Poll SIDs via external command as a fallback
                    if not detected_sid:
                        post_sids = self._get_active_sids()
                        new_sids = post_sids - pre_sids
                        if new_sids:
                            detected_sid = list(new_sids)[0]
                            logger.info(f"✨ Captured SID from polling: {detected_sid}")

            # Close child if still running
            if child.isalive():
                child.close()

            if detected_sid:
                return detected_sid

            # Final check if we missed it
            post_sids = self._get_active_sids()
            new_sids = post_sids - pre_sids
            if new_sids:
                return list(new_sids)[0]

            logger.error("❌ Jules failed to register a session within timeout.")
            return None

        except Exception as e:
            logger.error(f"Failed to launch Jules: {e}")
            return None

    def wait_for_completion(self, sid: str) -> bool:
        """
        Monitors the session status until it reaches 'Completed'.
        """
        logger.info(f"Monitoring status for SID: {sid}")

        # If mission was already detected as complete during launch, return True immediately
        if self.mission_complete:
            logger.info("✅ Mission Complete flag set during launch.")
            return True

        while True:
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

                display_status = " ".join(status_line.split()[4:])
                logger.info(f"Jules Status: {display_status}")
                time.sleep(20)

            except Exception as e:
                logger.error(f"Error monitoring status: {e}")
                time.sleep(10)

    def teleport_and_sync(self, sid: str, target_root: Path) -> bool:
        """
        Runs teleport in a temp folder and syncs src/ and tests/ to target_root.
        """
        logger.info(f"📥 Running authoritative teleport for SID {sid}...")

        temp_dir = target_root / f"jules_relay_{sid}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
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

            dirs_to_sync = ["src", "tests"]
            files_to_sync = ["requirements.txt"]

            for d in dirs_to_sync:
                src_path = source_folder / d
                dst_path = target_root / d
                if src_path.exists():
                    logger.info(f"Syncing directory: {d}")
                    if dst_path.exists():
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)

            for f in files_to_sync:
                src_file = source_folder / f
                dst_file = target_root / f
                if src_file.exists():
                    logger.info(f"Syncing file: {f}")
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
                logger.debug(f"Cleaned up {temp_dir}")
