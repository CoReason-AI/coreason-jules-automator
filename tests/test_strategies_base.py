import pytest
from coreason_jules_automator.strategies.base import DefenseStrategy, DefenseResult

class ConcreteDefense(DefenseStrategy):
    def execute(self, context):
        return super().execute(context)

def test_abstract_base_coverage():
    """Test to cover abstract base class method."""
    defense = ConcreteDefense()
    result = defense.execute({})
    assert result is None
