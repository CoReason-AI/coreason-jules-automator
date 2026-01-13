from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DefenseResult:
    """Result of a defense strategy execution."""

    success: bool
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DefenseStrategy(ABC):
    """Abstract base class for defense strategies."""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        """
        Executes the defense strategy.

        Args:
            context: Context dictionary containing necessary information (e.g., branch_name).

        Returns:
            DefenseResult indicating success or failure.
        """
        pass
