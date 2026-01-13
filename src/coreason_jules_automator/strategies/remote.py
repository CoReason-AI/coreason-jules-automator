import time
from typing import Any, Dict, List, Optional

from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class RemoteDefenseStrategy(DefenseStrategy):
    """
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    Wraps GitHubInterface and JanitorService.
    """

    def __init__(
        self,
        github: GitHubInterface,
        janitor: JanitorService,
        git: GitInterface,
        event_emitter: Optional[EventEmitter] = None,
    ):
        super().__init__(event_emitter)
        self.github = github
        self.janitor = janitor
        self.git = git

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        branch_name = context.get("branch_name")
        if not branch_name:
            return DefenseResult(success=False, message="Missing branch_name in context")

        self.event_emitter.emit(AutomationEvent(type=EventType.PHASE_START, message="Executing Line 2: Remote Defense"))

        # 1. Push Code
        try:
            self.event_emitter.emit(AutomationEvent(type=EventType.CHECK_RUNNING, message="Pushing Code"))
            commit_msg = self.janitor.sanitize_commit(f"feat: implementation for {branch_name}")
            self.git.push_to_branch(branch_name, commit_msg)
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.CHECK_RESULT,
                    message="Code pushed successfully",
                    payload={"status": "pass"},
                )
            )
        except RuntimeError as e:
            logger.error(f"Failed to push code: {e}")
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.CHECK_RESULT,
                    message=f"Failed to push code: {e}",
                    payload={"status": "fail", "error": str(e)},
                )
            )
            return DefenseResult(success=False, message=f"Failed to push code: {e}")

        # 2. Poll Checks
        max_poll_attempts = 10
        self.event_emitter.emit(
            AutomationEvent(
                type=EventType.CHECK_RUNNING,
                message="Polling CI Checks",
                payload={"max_attempts": max_poll_attempts},
            )
        )

        for i in range(max_poll_attempts):
            try:
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RUNNING,
                        message="Waiting for checks...",
                        payload={"attempt": i + 1, "max_attempts": max_poll_attempts},
                    )
                )

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
                        self.event_emitter.emit(
                            AutomationEvent(
                                type=EventType.CHECK_RESULT,
                                message="Line 2 defense passed. Success!",
                                payload={"status": "pass"},
                            )
                        )
                        return DefenseResult(success=True, message="CI checks passed")
                    else:
                        # Red - Get logs and summarize
                        summary = self._handle_ci_failure(checks)
                        self.event_emitter.emit(
                            AutomationEvent(
                                type=EventType.CHECK_RESULT,
                                message=f"CI Failure: {summary}",
                                payload={"status": "fail", "summary": summary},
                            )
                        )
                        return DefenseResult(success=False, message=summary)

                time.sleep(2)  # Wait before next poll

            except RuntimeError as e:
                logger.warning(f"Failed to poll checks: {e}")
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.ERROR, message=f"Poll attempt failed: {e}", payload={"error": str(e)}
                    )
                )
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
            log_snippet = (
                f"Check {failed_check.get('name', 'unknown')} failed. URL: {failed_check.get('url', 'unknown')}"
            )
            summary = self.janitor.summarize_logs(log_snippet)
            logger.info(f"Janitor Summary: {summary}")
            return summary

        return "CI checks failed but could not identify specific check failure."
