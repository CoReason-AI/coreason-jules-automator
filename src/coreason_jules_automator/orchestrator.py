# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import time
from typing import Any, List

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.llm.provider import LLMProvider
from coreason_jules_automator.utils.logger import logger


class Orchestrator:
    """
    The Brain of the Hybrid Vibe Runner.
    Manages the 'Two-Line Defense' state machine.
    """

    def __init__(self) -> None:
        self.gemini = GeminiInterface()
        self.github = GitHubInterface()
        self.janitor = LLMProvider()
        self.agent = JulesAgent()

    def run_cycle(self, task_description: str, branch_name: str) -> bool:
        """
        Executes the full development cycle:
        Agent -> Line 1 (Gemini) -> Line 2 (GitHub CI) -> Success/Retry.
        """
        settings = get_settings()
        logger.info(f"Starting orchestration cycle for branch: {branch_name}")

        attempt = 0
        while attempt < settings.max_retries:
            attempt += 1
            logger.info(f"Iteration {attempt}/{settings.max_retries}")

            # 1. Agent generates code (simulated by start task, but practically we wait for agent to finish)
            # In this architecture, we assume Agent runs locally and modifies files.
            # We trigger the agent, wait for it to finish (or it runs interactively).
            # Then we validate.

            # Start Agent
            try:
                self.agent.start(task_description)
            except Exception as e:
                logger.error(f"Agent failed to execute: {e}")
                return False

            # 2. Line 1: Fast Local Checks
            if not self._line_1_defense():
                logger.warning("Line 1 defense failed. Feedback sent to Agent (simulated). Retrying...")
                # In a real loop, we would feed feedback back to agent.
                # Here, we just loop back.
                # To simulate feedback, we could append failure to next task description?
                continue

            # 3. Line 2: Slow Remote Checks (The Truth)
            if self._line_2_defense(branch_name):
                logger.info("Line 2 defense passed. Success!")
                return True
            else:
                logger.warning("Line 2 defense failed. Retrying...")
                # Feedback is handled inside _line_2_defense via Janitor

        logger.error("Max retries reached. Task failed.")
        return False

    def _line_1_defense(self) -> bool:
        """
        Executes Gemini Security Scan and Code Review.
        Returns True if pass, False if fail.
        """
        settings = get_settings()
        logger.info("Executing Line 1: Local Defense")

        # Security Scan
        if "security" in settings.extensions_enabled:
            try:
                self.gemini.security_scan()
            except RuntimeError:  # pragma: no cover
                return False

        # Code Review
        if "code-review" in settings.extensions_enabled:
            try:
                self.gemini.code_review()
            except RuntimeError as e:  # pragma: no cover
                logger.error(f"Code review failed: {e}")  # pragma: no cover
                return False

        return True

    def _line_2_defense(self, branch_name: str) -> bool:
        """
        Executes GitHub CI/CD loop.
        Pushes code, polls checks, uses Janitor for feedback.
        """
        logger.info("Executing Line 2: Remote Defense")

        # 1. Push Code
        try:
            commit_msg = self.janitor.sanitize_commit(f"feat: implementation for {branch_name}")
            self.github.push_to_branch(branch_name, commit_msg)
        except RuntimeError as e:
            logger.error(f"Failed to push code: {e}")
            return False

        # 2. Poll Checks
        # We poll for a bit. In reality, we might wait minutes.
        # We'll use a simplified polling loop here with timeout.
        max_poll_attempts = 10
        for _ in range(max_poll_attempts):
            try:
                checks = self.github.get_pr_checks()
                # Analyze checks
                # checks is a list of dicts. We look for 'status' and 'conclusion'.
                # status: completed, queued, in_progress
                # conclusion: success, failure, etc.

                all_completed = True
                any_failure = False

                # If no checks found, it might mean they haven't started yet.
                if not checks:
                    time.sleep(2)
                    continue

                for check in checks:
                    if check["status"] != "completed":
                        all_completed = False
                    elif check["conclusion"] != "success":
                        any_failure = True

                if all_completed:
                    if not any_failure:
                        return True  # Green
                    else:
                        # Red - Get logs and summarize
                        self._handle_ci_failure(checks)
                        return False

                time.sleep(2)  # Wait before next poll

            except RuntimeError as e:
                logger.warning(f"Failed to poll checks: {e}")
                time.sleep(2)

        logger.error("Line 2 timeout: Checks did not complete.")
        return False

    def _handle_ci_failure(self, checks: List[Any]) -> None:
        """
        Uses Janitor to summarize failure logs.
        """
        logger.info("Analyzing CI failure...")
        # Find failed check
        failed_check = next((c for c in checks if c["conclusion"] != "success"), None)
        if failed_check:
            # In a real world, we would fetch logs via gh run view ...
            # Here we simulate by using the check name/url
            log_snippet = f"Check {failed_check['name']} failed. URL: {failed_check['url']}"
            summary = self.janitor.summarize_logs(log_snippet)
            logger.info(f"Janitor Summary: {summary}")  # pragma: no cover
            # This summary would normally be fed back to Agent.
