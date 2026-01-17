from typing import Protocol

from coreason_jules_automator.domain.context import OrchestrationContext, StrategyResult


class DefenseStep(Protocol):
    """Protocol for a single step in the defense pipeline."""

    async def execute(self, context: OrchestrationContext) -> StrategyResult:
        """
        Executes the defense step asynchronously.

        Args:
            context: OrchestrationContext containing necessary information.

        Returns:
            StrategyResult indicating success or failure.
        """
        ...  # pragma: no cover
