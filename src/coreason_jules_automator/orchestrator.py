# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import random
import string
from pathlib import Path
from typing import List, Optional, Tuple

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.base import DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class Orchestrator:
    """
    The Brain of the Coreason Jules Automator.
    Manages the 'Two-Line Defense' state machine using injected strategies.
    Refactored to support Remote Session + Teleport workflow.
    """

    def __init__(
        self,
        agent: JulesAgent,
        strategies: List[DefenseStrategy],
        event_emitter: Optional[EventEmitter] = None,
        git_interface: Optional[GitInterface] = None,
        janitor_service: Optional[JanitorService] = None,
    ) -> None:
        self.agent = agent
        self.strategies = strategies
        self.event_emitter = event_emitter or LoguruEmitter()
        self.git = git_interface
        self.janitor = janitor_service

    def run_cycle(self, task_description: str, branch_name: str) -> Tuple[bool, str]:
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

            # --- PHASE 1: REMOTE GENERATION & TELEPORT ---
            try:
                # 1. Launch Session
                launch_event = AutomationEvent(
                    type=EventType.CHECK_RUNNING, message="Launching Remote Jules Session..."
                )
                self.event_emitter.emit(launch_event)
                sid = self.agent.launch_session(task_description)

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
                success_wait = self.agent.wait_for_completion(sid)

                if not success_wait:
                    raise RuntimeError(f"Session {sid} did not complete successfully.")

                # 3. Teleport & Sync
                self.event_emitter.emit(
                    AutomationEvent(type=EventType.CHECK_RUNNING, message="Teleporting code to local workspace...")
                )
                success_sync = self.agent.teleport_and_sync(sid, Path.cwd())

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
                result = strategy.execute(context={"branch_name": branch_name, "sid": sid})
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

    def run_campaign(self, task: str, base_branch: str = "develop", iterations: int = 10) -> None:
        """
        Runs a campaign of multiple iterations to solve a task.
        """
        if not self.git or not self.janitor:
            raise RuntimeError("GitInterface and JanitorService are required for Campaign mode.")

        # Generate ID
        run_id = "".join(random.choices(string.digits, k=10))
        agg_branch = f"vibe_run_{run_id}"

        logger.info(f"Starting Campaign ID: {run_id}. Aggregation Branch: {agg_branch}")
        self.git.checkout_new_branch(agg_branch, base_branch)

        for i in range(1, iterations + 1):
            iter_branch = f"vibe_run_{run_id}_{i:03d}"
            logger.info(f"--- Campaign Iteration {i}/{iterations}: {iter_branch} ---")

            try:
                self.git.checkout_new_branch(iter_branch, base_branch)
                success, feedback = self.run_cycle(task, iter_branch)

                if success:
                    logger.info(f"Iteration {i} Succeeded. Merging into {agg_branch}...")
                    raw_log = self.git.get_commit_log(base_branch, iter_branch)
                    clean_msg = self.janitor.professionalize_commit(raw_log)
                    self.git.merge_squash(iter_branch, agg_branch, clean_msg)
                else:
                    logger.warning(f"Iteration {i} Failed: {feedback}. Continuing to next iteration.")

            except Exception as e:
                logger.error(f"Iteration {i} encountered an error: {e}")
                # Continue to next iteration
