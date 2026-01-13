from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy


class MockStrategy(DefenseStrategy):
    def __init__(self, success: bool = True, message: str = ""):
        self.success = success
        self.message = message

    def execute(self, context: Any) -> DefenseResult:
        return DefenseResult(success=self.success, message=self.message)


@pytest.fixture
def mock_agent() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_strategy_success() -> MagicMock:
    strategy = MagicMock(spec=DefenseStrategy)
    strategy.execute.return_value = DefenseResult(success=True)
    return strategy


@pytest.fixture
def mock_strategy_fail() -> MagicMock:
    strategy = MagicMock(spec=DefenseStrategy)
    strategy.execute.return_value = DefenseResult(success=False, message="Fail")
    return strategy


def test_orchestrator_init(mock_agent: MagicMock, mock_strategy_success: MagicMock) -> None:
    """Test Orchestrator initialization with DI."""
    strategies = [mock_strategy_success]
    orch = Orchestrator(agent=mock_agent, strategies=strategies)
    assert orch.agent == mock_agent
    assert orch.strategies == strategies


def test_run_cycle_success(mock_agent: MagicMock, mock_strategy_success: MagicMock) -> None:
    """Test full cycle success."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        orch = Orchestrator(agent=mock_agent, strategies=[mock_strategy_success])
        assert orch.run_cycle("task", "branch") is True

        mock_agent.start.assert_called_with("task")
        mock_strategy_success.execute.assert_called_with(context={"branch_name": "branch"})


def test_run_cycle_agent_fail(mock_agent: MagicMock, mock_strategy_success: MagicMock) -> None:
    """Test cycle aborts if agent fails."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        mock_agent.start.side_effect = Exception("Agent died")

        orch = Orchestrator(agent=mock_agent, strategies=[mock_strategy_success])
        assert orch.run_cycle("task", "branch") is False


def test_run_cycle_strategy_fail_retry(mock_agent: MagicMock) -> None:
    """Test retry loop on strategy failure."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        # Strategy fails first time, succeeds second time
        strategy = MagicMock(spec=DefenseStrategy)
        strategy.execute.side_effect = [
            DefenseResult(success=False, message="Fail"),
            DefenseResult(success=True)
        ]

        orch = Orchestrator(agent=mock_agent, strategies=[strategy])
        assert orch.run_cycle("task", "branch") is True

        assert mock_agent.start.call_count == 2
        assert strategy.execute.call_count == 2


def test_run_cycle_multiple_strategies_fail(mock_agent: MagicMock) -> None:
    """Test multi-strategy failure stops at first failure."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 2
        mock_get_settings.return_value = mock_settings

        strat1 = MagicMock(spec=DefenseStrategy)
        strat1.execute.return_value = DefenseResult(success=True)

        strat2 = MagicMock(spec=DefenseStrategy)
        strat2.execute.return_value = DefenseResult(success=False, message="Fail")

        orch = Orchestrator(agent=mock_agent, strategies=[strat1, strat2])
        assert orch.run_cycle("task", "branch") is False

        # strat1 called twice (once per retry)
        assert strat1.execute.call_count == 2
        # strat2 called twice (once per retry)
        assert strat2.execute.call_count == 2


def test_run_cycle_max_retries(mock_agent: MagicMock, mock_strategy_fail: MagicMock) -> None:
    """Test max retries reached."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 2
        mock_get_settings.return_value = mock_settings

        orch = Orchestrator(agent=mock_agent, strategies=[mock_strategy_fail])
        assert orch.run_cycle("task", "branch") is False
        assert mock_agent.start.call_count == 2
