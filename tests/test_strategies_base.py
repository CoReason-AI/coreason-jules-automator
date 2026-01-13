from typing import Any, Dict

import pytest
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy


class ConcreteDefense(DefenseStrategy):
    async def execute(self, context: Dict[str, Any]) -> DefenseResult:
        return DefenseResult(success=True)


@pytest.mark.asyncio
async def test_abstract_base_coverage() -> None:
    """Test to cover abstract base class method."""
    defense = ConcreteDefense()
    result = await defense.execute({})
    assert result.success
