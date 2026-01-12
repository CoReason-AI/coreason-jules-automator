# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import sys
from pathlib import Path
from typing import Optional

import pexpect

from coreason_jules_automator.utils.logger import logger


class JulesAgent:
    """
    Wrapper around the Jules agent using pexpect.
    Handles context injection and auto-replies.
    """

    def __init__(self, executable: str = "jules") -> None:
        self.executable = executable
        self.child: Optional[pexpect.spawn] = None

    def start(self, task: str) -> None:
        """
        Starts the Jules agent with the given task.
        Injects SPEC.md context if available.
        """
        # Check for SPEC.md
        spec_path = Path("SPEC.md")
        context = ""
        if spec_path.exists():
            try:
                spec_content = spec_path.read_text(encoding="utf-8")
                context = (
                    f"You are working under the supervision of Conductor. "
                    f"Here is the specification:\n{spec_content}\n\n"
                )
                logger.info("Injected SPEC.md context.")
            except Exception as e:
                logger.warning(f"Failed to read SPEC.md: {e}")

        full_prompt = context + task
        logger.info(f"Starting Jules with task: {task[:50]}...")

        try:
            self.child = pexpect.spawn(self.executable, encoding="utf-8", timeout=300)
            # ignore logging to stdout in production or configure properly
            self.child.logfile = sys.stdout

            # Send the task
            self.child.sendline(full_prompt)

            # Start the interaction loop
            self._interaction_loop()

        except pexpect.ExceptionPexpect as e:
            logger.error(f"Failed to start Jules: {e}")
            raise RuntimeError(f"Failed to start Jules: {e}") from e

    def _interaction_loop(self) -> None:
        """
        Monitors Jules output and handles auto-replies.
        """
        if not self.child:
            return

        patterns = [
            "Should I",  # Trigger for auto-reply
            pexpect.EOF,
            pexpect.TIMEOUT,
        ]

        while True:
            try:
                index = self.child.expect(patterns, timeout=60)

                if index == 0:  # "Should I" matched
                    logger.info("Detected question from Jules. Auto-replying.")
                    self.child.sendline("Use your best judgment.")
                elif index == 1:  # EOF
                    logger.info("Jules finished execution.")  # pragma: no cover
                    break
                elif index == 2:  # TIMEOUT
                    # Check if process is still alive. If so, continue waiting.
                    if not self.child.isalive():
                        break
                    # Just continue loop
                    continue

            except pexpect.EOF:
                break
            except pexpect.TIMEOUT:
                # Check explicitly if alive
                if not self.child.isalive():
                    break

        self.child.close()
        if self.child.exitstatus != 0:  # pragma: no cover
            logger.warning(f"Jules exited with status {self.child.exitstatus}")
