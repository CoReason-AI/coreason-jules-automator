from typing import Any, Dict, Optional

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import AutomationEvent, EventEmitter, EventType
from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class LocalDefenseStrategy(DefenseStrategy):
    """
    Implements 'Line 1' of the defense strategy (Local Security & Code Review).
    Wraps GeminiInterface.
    """

    def __init__(self, gemini: GeminiInterface, event_emitter: Optional[EventEmitter] = None):
        super().__init__(event_emitter)
        self.gemini = gemini

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
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
                self.gemini.security_scan()
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
                self.gemini.code_review()
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
