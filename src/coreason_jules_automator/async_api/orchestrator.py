import random
import string
from pathlib import Path
from typing import List, Optional, Tuple

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGitInterface
from coreason_jules_automator.async_api.strategies import AsyncDefenseStrategy
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.utils.logger import logger


class AsyncOrchestrator:
    """
    The Async Brain of the Coreason Jules Automator.
    Manages the 'Two-Line Defense' state machine using injected strategies.
    Refactored to support Remote Session + Teleport workflow asynchronously.
    """

    def __init__(
        self,
        agent: AsyncJulesAgent,
        strategies: List[AsyncDefenseStrategy],
        event_emitter: Optional[EventEmitter] = None,
        git_interface: Optional[AsyncGitInterface] = None,
        janitor_service: Optional[JanitorService] = None,
        llm_client: Optional[AsyncLLMClient] = None,
    ) -> None:
        self.agent = agent
        self.strategies = strategies
        self.event_emitter = event_emitter or LoguruEmitter()
        self.git = git_interface
        self.janitor = janitor_service
        self.llm_client = llm_client

    async def run_cycle(self, task_description: str, branch_name: str) -> Tuple[bool, str]:
        """
        Executes the full development cycle:
        Agent Launch -> Wait -> Teleport -> Strategies -> Success/Retry.
        Returns (success, feedback_log).
        """
        settings = get_settings()
        self.event_emitter.emit(
            AutomationEvent(
                type=EventType.CYCLE_START,
                message=f"Starting orchestration cycle for branch: {branch_name}",
                payload={"task": task_description, "branch": branch_name},
            )
        )

        attempt = 0
        last_error = ""
        while attempt < settings.max_retries:
            attempt += 1
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.PHASE_START,
                    message=f"Iteration {attempt}/{settings.max_retries}",
                    payload={"attempt": attempt, "max_retries": settings.max_retries},
                )
            )

            # Prepare prompt with feedback if retry
            current_task = task_description
            if attempt > 1 and last_error:
                prefix = "\n\nIMPORTANT: The previous attempt failed with the following error:\n"
                current_task = f"{task_description}{prefix}{last_error}"
                logger.info("Appending feedback to task description for retry.")

            # --- PHASE 1: REMOTE GENERATION & TELEPORT ---
            try:
                # 1. Launch Session
                self.event_emitter.emit(
                    AutomationEvent(type=EventType.CHECK_RUNNING, message="Launching Remote Jules Session...")
                )
                sid = await self.agent.launch_session(current_task)

                if not sid:
                    raise RuntimeError("Failed to obtain Session ID (SID).")

                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT, message=f"Session Started: {sid}", payload={"sid": sid}
                    )
                )

                # 2. Monitor for Completion
                self.event_emitter.emit(
                    AutomationEvent(type=EventType.CHECK_RUNNING, message=f"Waiting for SID {sid} to complete...")
                )
                success_wait = await self.agent.wait_for_completion(sid)

                if not success_wait:
                    raise RuntimeError(f"Session {sid} did not complete successfully.")

                # 3. Teleport & Sync
                self.event_emitter.emit(
                    AutomationEvent(type=EventType.CHECK_RUNNING, message="Teleporting code to local workspace...")
                )
                success_sync = await self.agent.teleport_and_sync(sid, Path.cwd())

                if not success_sync:
                    raise RuntimeError("Failed to sync remote code to local repository.")

                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.CHECK_RESULT, message="Code synced successfully.", payload={"status": "pass"}
                    )
                )

            except Exception as e:
                error_msg = f"Agent workflow failed: {e}"
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.ERROR,
                        message=error_msg,
                        payload={"error": str(e)},
                    )
                )
                return False, error_msg

            # --- PHASE 2: DEFENSE STRATEGIES ---
            cycle_passed = True
            for strategy in self.strategies:
                result = await strategy.execute(context={"branch_name": branch_name, "sid": sid})
                if not result.success:
                    logger.warning(f"Strategy {strategy.__class__.__name__} failed: {result.message}")
                    last_error = result.message
                    cycle_passed = False
                    # The strategies (specifically Line 2 / Janitor) generate the feedback for the next loop
                    break

            if cycle_passed:
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.PHASE_START,
                        message="All defense strategies passed. Success!",
                        payload={"status": "success"},
                    )
                )
                return True, "Success"
            else:
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.PHASE_START,
                        message="Defense cycle failed. Retrying...",
                        payload={"status": "retry"},
                    )
                )

        self.event_emitter.emit(
            AutomationEvent(
                type=EventType.ERROR,
                message="Max retries reached. Task failed.",
                payload={"status": "failed"},
            )
        )
        return False, last_error

    async def run_campaign(self, task: str, base_branch: str = "develop", iterations: Optional[int] = 50) -> None:
        """
        Runs a campaign of multiple iterations to solve a task.
        If iterations is 0 or None, it runs in Infinite Mode (up to a safety limit).
        """
        if not self.git or not self.janitor:
            raise RuntimeError("GitInterface and JanitorService are required for Campaign mode.")

        # Determine limit
        limit = iterations if iterations and iterations > 0 else 1000
        is_infinite = not iterations or iterations == 0
        logger.info(f"Campaign Mode: {'Infinite (Safety Limit: 1000)' if is_infinite else f'Fixed ({limit})'}")

        # Generate ID
        run_id = "".join(random.choices(string.digits, k=10))
        agg_branch = f"vibe_run_{run_id}"

        logger.info(f"Starting Campaign ID: {run_id}. Aggregation Branch: {agg_branch}")
        await self.git.checkout_new_branch(agg_branch, base_branch)

        i = 0
        while i < limit:
            i += 1
            iter_branch = f"vibe_run_{run_id}_{i:03d}"
            logger.info(f"--- Campaign Iteration {i}/{limit}: {iter_branch} ---")

            try:
                # Checkout iteration branch from AGGREGATION branch
                await self.git.checkout_new_branch(iter_branch, agg_branch, pull_base=False)
                success, feedback = await self.run_cycle(task, iter_branch)

                if success:
                    logger.info(f"Iteration {i} Succeeded. Merging into {agg_branch}...")
                    raw_log = await self.git.get_commit_log(agg_branch, iter_branch)

                    # Sans-I/O Refactor: Professionalize Commit
                    clean_msg = raw_log  # Default fallback
                    if self.janitor and self.llm_client:
                        try:
                            req = self.janitor.build_professionalize_request(raw_log)
                            # Simple single attempt for now, bypassing original retry logic for brevity in refactor
                            # or implementing a simple loop here if needed.
                            # Replicating simple retry loop here:
                            for _ in range(3):
                                try:
                                    resp = await self.llm_client.execute(req)
                                    resp_text = resp.content
                                    parsed = self.janitor.parse_professionalize_response(raw_log, resp_text)
                                    clean_msg = parsed
                                    break
                                except Exception:
                                    continue
                        except Exception as e:
                            logger.error(f"Professionalize commit failed: {e}")
                    else:
                        if self.janitor:
                            clean_msg = self.janitor.sanitize_commit(raw_log)

                    await self.git.merge_squash(iter_branch, agg_branch, clean_msg)

                    # Cleanup
                    await self.git.delete_branch(iter_branch)

                    # Termination Check
                    if self.agent.mission_complete:
                        logger.info("🎉 Mission Complete! '100% of the requirements is met' signal received.")
                        break
                else:
                    logger.warning(f"Iteration {i} Failed: {feedback}. Continuing to next iteration.")
                    await self.git.delete_branch(iter_branch)

            except Exception as e:
                logger.error(f"Iteration {i} encountered an error: {e}")
                # Try to cleanup
                try:
                    await self.git.delete_branch(iter_branch)
                except Exception:
                    pass
