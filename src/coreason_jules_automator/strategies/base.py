from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from coreason_jules_automator.events import EventEmitter, LoguruEmitter


@dataclass
class DefenseResult:
    """Result of a defense strategy execution."""

    success: bool
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DefenseStrategy(ABC):
    """Abstract base class for defense strategies."""

    def __init__(self, event_emitter: Optional[EventEmitter] = None) -> None:
        self.event_emitter = event_emitter or LoguruEmitter()

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> DefenseResult:
        """
        Executes the defense strategy.

        Args:
            context: Context dictionary containing necessary information (e.g., branch_name).

        Returns:
            DefenseResult indicating success or failure.
        """
        pass
