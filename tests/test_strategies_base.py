import pytest
from typing import Any, Dict

from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy


class ConcreteDefense(DefenseStrategy):
    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        # We need to ignore type error because we are calling abstract method with trivial body
        # which usually shouldn't be called, but we are doing it for coverage.
        return super().execute(context)  # type: ignore[safe-super, no-any-return]


def test_abstract_base_coverage() -> None:
    """Test to cover abstract base class method."""
    defense = ConcreteDefense()
    result = defense.execute({})
    assert result is None
