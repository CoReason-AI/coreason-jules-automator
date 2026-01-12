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
from typing import List

from coreason_jules_automator.utils.logger import logger


class GeminiInterface:
    """
    Interface for interacting with the Gemini CLI tools.
    Implements 'Line 1' of the defense strategy (Local Security & Code Review).
    """

    def __init__(self, executable: str = "gemini") -> None:
        self.executable = executable
        if not shutil.which(self.executable):
            # We don't raise an error here to allow for testing in environments without gemini
            logger.warning(f"Gemini executable '{self.executable}' not found in PATH.")

    def _run_command(self, args: List[str]) -> str:
        """
        Executes a gemini command.

        Args:
            args: List of arguments to pass to the gemini command.

        Returns:
            The standard output of the command if successful.

        Raises:
            RuntimeError: If the command fails (non-zero exit code).
        """
        command = [self.executable] + args
        logger.debug(f"Executing: {' '.join(command)}")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except Exception as e:
            raise RuntimeError(f"Failed to execute gemini command: {e}") from e

        if result.returncode != 0:
            error_msg = (
                f"Gemini command failed (Exit {result.returncode}):\n{result.stderr.strip() or result.stdout.strip()}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("Gemini command successful")
        return str(result.stdout.strip())

    def security_scan(self, path: str = ".") -> str:
        """
        Runs the gemini security scan on the specified path.

        Args:
            path: The path to scan.

        Returns:
            The output of the security scan.
        """
        logger.info(f"Starting security scan on {path}")
        return self._run_command(["security", "scan", path])

    def code_review(self, path: str = ".") -> str:
        """
        Runs the gemini code review on the specified path.

        Args:
            path: The path to review.

        Returns:
            The output of the code review.
        """
        logger.info(f"Starting code review on {path}")
        return self._run_command(["code-review", path])
