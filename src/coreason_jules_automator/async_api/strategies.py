import asyncio
from typing import Any, Dict, List, Optional, Protocol

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitInterface, AsyncGitHubInterface
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.base import DefenseResult
from coreason_jules_automator.utils.logger import logger


class AsyncDefenseStrategy(Protocol):
    """Protocol for async defense strategies."""

    async def execute(self, context: Dict[str, Any]) -> DefenseResult:
        """
        Executes the defense strategy asynchronously.

        Args:
            context: Context dictionary containing necessary information.

        Returns:
            DefenseResult indicating success or failure.
        """
        ...


class AsyncLocalDefenseStrategy:
    """
    Implements 'Line 1' of the defense strategy (Local Security & Code Review).
    Wraps AsyncGeminiInterface.
    """

    def __init__(self, gemini: AsyncGeminiInterface, event_emitter: Optional[EventEmitter] = None):
        self.gemini = gemini
        self.event_emitter = event_emitter or LoguruEmitter()

    async def execute(self, context: Dict[str, Any]) -> DefenseResult:
        settings = get_settings()
        self.event_emitter.emit(AutomationEvent(type=EventType.PHASE_START, message="Executing Line 1: Local Defense"))
        passed = True
        errors = []

        # Security Scan
        if "security" in settings.extensions_enabled:
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.CHECK_RUNNING,
                    message="Running Security Scan",
                    payload={"check": "security"},
                )
            )
            try:
                await self.gemini.security_scan()
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT,
                        message="Security Scan passed",
                        payload={"check": "security", "status": "pass"},
                    )
                )
            except RuntimeError as e:
                errors.append(f"Security Scan failed: {e}")
                passed = False
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT,
                        message=f"Security Scan failed: {e}",
                        payload={"check": "security", "status": "fail", "error": str(e)},
                    )
                )

        if not passed:
            return DefenseResult(success=False, message="\n".join(errors))

        # Code Review
        if "code-review" in settings.extensions_enabled:
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.CHECK_RUNNING,
                    message="Running Code Review",
                    payload={"check": "code-review"},
                )
            )
            try:
                await self.gemini.code_review()
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT,
                        message="Code Review passed",
                        payload={"check": "code-review", "status": "pass"},
                    )
                )
            except RuntimeError as e:
                logger.error(f"Code review failed: {e}")
                errors.append(f"Code Review failed: {e}")
                passed = False
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT,
                        message=f"Code Review failed: {e}",
                        payload={"check": "code-review", "status": "fail", "error": str(e)},
                    )
                )

        if passed:
            return DefenseResult(success=True, message="Local checks passed")
        else:
            return DefenseResult(success=False, message="\n".join(errors))


class AsyncRemoteDefenseStrategy:
    """
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    Wraps AsyncGitHubInterface and JanitorService.
    """

    def __init__(
        self,
        github: AsyncGitHubInterface,
        janitor: JanitorService,
        git: AsyncGitInterface,
        llm_client: Optional[AsyncLLMClient] = None,
        event_emitter: Optional[EventEmitter] = None,
    ):
        self.github = github
        self.janitor = janitor
        self.git = git
        self.llm_client = llm_client
        self.event_emitter = event_emitter or LoguruEmitter()

    async def execute(self, context: Dict[str, Any]) -> DefenseResult:
        branch_name = context.get("branch_name")
        if not branch_name:
            return DefenseResult(success=False, message="Missing branch_name in context")

        sid = context.get("sid", "unknown")

        self.event_emitter.emit(AutomationEvent(type=EventType.PHASE_START, message="Executing Line 2: Remote Defense"))

        # 1. Push Code
        try:
            self.event_emitter.emit(AutomationEvent(type=EventType.CHECK_RUNNING, message="Pushing Code"))

            # Traceability: Add SID to commit
            base_msg = f"feat: implementation for {branch_name} (SID: {sid})"
            commit_msg = self.janitor.sanitize_commit(base_msg)

            changes_pushed = await self.git.push_to_branch(branch_name, commit_msg)

            if not changes_pushed:
                msg = "No changes detected to push. Agent produced identical code."
                self.event_emitter.emit(
                    AutomationEvent(type=EventType.CHECK_RESULT, message=msg, payload={"status": "warn"})
                )
                return DefenseResult(success=True, message="No changes detected. Task completed.")

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

                checks = await self.github.get_pr_checks()
                # Analyze checks
                all_completed = True
                any_failure = False

                if not checks:
                    await asyncio.sleep(2)
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
                        summary = await self._handle_ci_failure(checks)
                        self.event_emitter.emit(
                            AutomationEvent(
                                type=EventType.CHECK_RESULT,
                                message=f"CI Failure: {summary}",
                                payload={"status": "fail", "summary": summary},
                            )
                        )
                        return DefenseResult(success=False, message=summary)

                await asyncio.sleep(2)  # Wait before next poll

            except RuntimeError as e:
                logger.warning(f"Failed to poll checks: {e}")
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.ERROR, message=f"Poll attempt failed: {e}", payload={"error": str(e)}
                    )
                )
                await asyncio.sleep(2)

        error_msg = "Line 2 timeout: Checks did not complete."
        logger.error(error_msg)
        return DefenseResult(success=False, message=error_msg)

    async def _handle_ci_failure(self, checks: List[Any]) -> str:
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

            # Sans-I/O: Build Request -> Execute -> Return
            if not self.llm_client:
                logger.warning("No LLM client available for log summarization.")
                return f"CI checks failed. {log_snippet}"

            try:
                req = self.janitor.build_summarize_request(log_snippet)
                # Async execution
                resp = await self.llm_client.execute(req)
                summary = resp.content
                logger.info(f"Janitor Summary: {summary}")
                return summary
            except Exception as e:
                logger.error(f"Janitor summarization failed: {e}")
                return "Log summarization failed. Please check the logs directly."

        return "CI checks failed but could not identify specific check failure."
