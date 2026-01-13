from typing import Any, Dict

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy
from coreason_jules_automator.utils.logger import logger


class LocalDefenseStrategy(DefenseStrategy):
    """
    Implements 'Line 1' of the defense strategy (Local Security & Code Review).
    Wraps GeminiInterface.
    """

    def __init__(self, gemini: GeminiInterface):
        self.gemini = gemini

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        settings = get_settings()
        logger.info("Executing Line 1: Local Defense")
        passed = True
        errors = []

        # Security Scan
        if "security" in settings.extensions_enabled:
            try:
                self.gemini.security_scan()
            except RuntimeError as e:
                errors.append(f"Security Scan failed: {e}")
                passed = False

        if not passed:
            return DefenseResult(success=False, message="\n".join(errors))

        # Code Review
        if "code-review" in settings.extensions_enabled:
            try:
                self.gemini.code_review()
            except RuntimeError as e:
                logger.error(f"Code review failed: {e}")
                errors.append(f"Code Review failed: {e}")
                passed = False

        if passed:
            return DefenseResult(success=True, message="Local checks passed")
        else:
            return DefenseResult(success=False, message="\n".join(errors))
