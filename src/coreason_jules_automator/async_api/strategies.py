from typing import List, Optional, Protocol, Tuple

from tenacity import AsyncRetrying, RetryError, retry_if_exception_type, stop_after_attempt, wait_exponential

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface, AsyncGitInterface
from coreason_jules_automator.config import Settings
from coreason_jules_automator.domain.context import OrchestrationContext, StrategyResult
from coreason_jules_automator.domain.scm import PullRequestStatus
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.utils.logger import logger


class TryAgain(Exception):
    """Internal exception to trigger retry in tenacity."""

    pass


class AsyncDefenseStrategy(Protocol):
    """Protocol for async defense strategies."""

    async def execute(self, context: OrchestrationContext) -> StrategyResult:
        """
        Executes the defense strategy asynchronously.

        Args:
            context: OrchestrationContext containing necessary information.

        Returns:
            StrategyResult indicating success or failure.
        """
        ...  # pragma: no cover


class AsyncLocalDefenseStrategy:
    """
    Implements 'Line 1' of the defense strategy (Local Security & Code Review).
    Wraps AsyncGeminiInterface.
    """

    def __init__(self, settings: Settings, gemini: AsyncGeminiInterface, event_emitter: Optional[EventEmitter] = None):
        self.settings = settings
        self.gemini = gemini
        self.event_emitter = event_emitter or LoguruEmitter()

    async def execute(self, context: OrchestrationContext) -> StrategyResult:
        self.event_emitter.emit(AutomationEvent(type=EventType.PHASE_START, message="Executing Line 1: Local Defense"))
        passed = True
        errors = []

        # Security Scan
        if "security" in self.settings.extensions_enabled:
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
            return StrategyResult(success=False, message="\n".join(errors))

        # Code Review
        if "code-review" in self.settings.extensions_enabled:
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
            return StrategyResult(success=True, message="Local checks passed")
        else:
            return StrategyResult(success=False, message="\n".join(errors))


class AsyncRemoteDefenseStrategy:
    """
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    Wraps AsyncGitHubInterface and JanitorService.
    """

    def __init__(
        self,
        settings: Settings,
        github: AsyncGitHubInterface,
        janitor: JanitorService,
        git: AsyncGitInterface,
        llm_client: Optional[AsyncLLMClient] = None,
        event_emitter: Optional[EventEmitter] = None,
    ):
        self.settings = settings
        self.github = github
        self.janitor = janitor
        self.git = git
        self.llm_client = llm_client
        self.event_emitter = event_emitter or LoguruEmitter()

    async def execute(self, context: OrchestrationContext) -> StrategyResult:
        branch_name = context.branch_name
        sid = context.session_id

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
                return StrategyResult(success=True, message="No changes detected. Task completed.")

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
            return StrategyResult(success=False, message=f"Failed to push code: {e}")

        # 2. Poll Checks
        return await self._run_ci_polling(branch_name)

    def _analyze_checks(self, checks: List[PullRequestStatus]) -> Tuple[bool, bool]:
        """Returns (all_completed, any_failure)."""
        if not checks:
            return False, False

        all_completed = True
        any_failure = False

        for check in checks:
            if check.status != "completed":
                all_completed = False
            elif check.conclusion != "success":
                any_failure = True

        return all_completed, any_failure

    async def _run_ci_polling(self, branch_name: str) -> StrategyResult:
        """
        Polls CI checks and returns the result using tenacity.
        """
        self.event_emitter.emit(
            AutomationEvent(
                type=EventType.CHECK_RUNNING,
                message="Polling CI Checks",
            )
        )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(30),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(TryAgain),
                reraise=False,
            ):
                with attempt:
                    self.event_emitter.emit(
                        AutomationEvent(
                            type=EventType.CHECK_RUNNING,
                            message=f"Polling attempt {attempt.retry_state.attempt_number}",
                            payload={"attempt": attempt.retry_state.attempt_number},
                        )
                    )

                    try:
                        checks = await self.github.get_pr_checks()
                    except RuntimeError as e:
                        logger.warning(f"Poll attempt failed: {e}")
                        raise TryAgain(f"Fetch failed: {e}") from e

                    all_completed, any_failure = self._analyze_checks(checks)

                    if not all_completed:
                        raise TryAgain("Checks not completed yet")

                    if not any_failure:
                        self.event_emitter.emit(
                            AutomationEvent(
                                type=EventType.CHECK_RESULT,
                                message="Line 2 defense passed. Success!",
                                payload={"status": "pass"},
                            )
                        )
                        return StrategyResult(success=True, message="CI checks passed")
                    else:
                        # Red - Get logs and summarize
                        summary = await self._handle_ci_failure(checks, branch_name)
                        self.event_emitter.emit(
                            AutomationEvent(
                                type=EventType.CHECK_RESULT,
                                message=f"CI Failure: {summary}",
                                payload={"status": "fail", "summary": summary},
                            )
                        )
                        return StrategyResult(success=False, message=summary)

        except RetryError:
            error_msg = "Line 2 timeout: Checks did not complete."
            logger.error(error_msg)
            return StrategyResult(success=False, message=error_msg)

        # Fallback if loop finishes without returning (should not happen with infinite retries/reraise=False but good for mypy)
        return StrategyResult(success=False, message="Polling loop exited unexpectedly")

    async def _handle_ci_failure(self, checks: List[PullRequestStatus], branch_name: str) -> str:
        """
        Uses Janitor to summarize failure logs.
        """
        logger.info("Analyzing CI failure...")
        # Find failed check
        failed_check = next((c for c in checks if c.conclusion != "success"), None)
        if failed_check:
            log_snippet = f"Check {failed_check.name} failed. URL: {failed_check.url}"

            # Get full logs if possible (Streamed)
            full_logs_list = []
            try:
                async for line in self.github.get_latest_run_log(branch_name):
                    full_logs_list.append(line)
                    # Limit to avoid RAM issues if very large
                    if len(full_logs_list) > 2000:
                        full_logs_list.pop(0)  # Keep tail
            except Exception as e:
                logger.error(f"Failed to stream logs: {e}")
                full_logs_list.append(f"Error streaming logs: {e}")

            full_logs = "\n".join(full_logs_list)
            log_snippet += f"\n\n--- Logs ---\n{full_logs}"

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
