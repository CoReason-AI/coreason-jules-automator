import time
from typing import Any, Dict, List

from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class RemoteDefenseStrategy(DefenseStrategy):
    """
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    Wraps GitHubInterface and JanitorService.
    """

    def __init__(self, github: GitHubInterface, janitor: JanitorService):
        self.github = github
        self.janitor = janitor

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        branch_name = context.get("branch_name")
        if not branch_name:
            return DefenseResult(success=False, message="Missing branch_name in context")

        logger.info("Executing Line 2: Remote Defense")

        # 1. Push Code
        try:
            commit_msg = self.janitor.sanitize_commit(f"feat: implementation for {branch_name}")
            self.github.push_to_branch(branch_name, commit_msg)
        except RuntimeError as e:
            logger.error(f"Failed to push code: {e}")
            return DefenseResult(success=False, message=f"Failed to push code: {e}")

        # 2. Poll Checks
        max_poll_attempts = 10
        for _ in range(max_poll_attempts):
            try:
                checks = self.github.get_pr_checks()
                # Analyze checks
                all_completed = True
                any_failure = False

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
                        logger.info("Line 2 defense passed. Success!")
                        return DefenseResult(success=True, message="CI checks passed")
                    else:
                        # Red - Get logs and summarize
                        summary = self._handle_ci_failure(checks)
                        return DefenseResult(success=False, message=summary)

                time.sleep(2)  # Wait before next poll

            except RuntimeError as e:
                logger.warning(f"Failed to poll checks: {e}")
                time.sleep(2)

        error_msg = "Line 2 timeout: Checks did not complete."
        logger.error(error_msg)
        return DefenseResult(success=False, message=error_msg)

    def _handle_ci_failure(self, checks: List[Any]) -> str:
        """
        Uses Janitor to summarize failure logs.
        """
        logger.info("Analyzing CI failure...")
        # Find failed check
        failed_check = next((c for c in checks if c["conclusion"] != "success"), None)
        if failed_check:
            log_snippet = f"Check {failed_check.get('name', 'unknown')} failed. URL: {failed_check.get('url', 'unknown')}"
            summary = self.janitor.summarize_logs(log_snippet)
            logger.info(f"Janitor Summary: {summary}")
            return summary

        return "CI checks failed but could not identify specific check failure."
