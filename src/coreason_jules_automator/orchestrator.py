# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

from typing import List, Optional

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType, LoguruEmitter
from coreason_jules_automator.strategies.base import DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class Orchestrator:
    """
    The Brain of the Coreason Jules Automator.
    Manages the 'Two-Line Defense' state machine using injected strategies.
    """

    def __init__(
        self,
        agent: JulesAgent,
        strategies: List[DefenseStrategy],
        event_emitter: Optional[EventEmitter] = None,
    ) -> None:
        self.agent = agent
        self.strategies = strategies
        self.event_emitter = event_emitter or LoguruEmitter()

    def run_cycle(self, task_description: str, branch_name: str) -> bool:
        """
        Executes the full development cycle:
        Agent -> Strategies -> Success/Retry.
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
        while attempt < settings.max_retries:
            attempt += 1
            self.event_emitter.emit(
                AutomationEvent(
                    type=EventType.PHASE_START,
                    message=f"Iteration {attempt}/{settings.max_retries}",
                    payload={"attempt": attempt, "max_retries": settings.max_retries},
                )
            )

            # 1. Agent generates code
            try:
                self.agent.start(task_description)
            except Exception as e:
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.ERROR,
                        message=f"Agent failed to execute: {e}",
                        payload={"error": str(e)},
                    )
                )
                return False

            # 2. Execute Defense Strategies
            cycle_passed = True
            for strategy in self.strategies:
                result = strategy.execute(context={"branch_name": branch_name})
                if not result.success:
                    # Strategy failure is logged by the strategy itself via events (ideally),
                    # but we also log high level warning here.
                    logger.warning(f"Strategy {strategy.__class__.__name__} failed: {result.message}")
                    cycle_passed = False
                    # Feedback loop simulated here; in real implementation would pass back to agent
                    break  # Break inner loop to retry outer loop

            if cycle_passed:
                self.event_emitter.emit(
                    AutomationEvent(
                        type=EventType.PHASE_START,
                        message="All defense strategies passed. Success!",
                        payload={"status": "success"},
                    )
                )
                return True
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
        return False
