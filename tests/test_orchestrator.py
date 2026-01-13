from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.strategies.base import DefenseResult

@pytest.fixture
def orchestrator():
    agent = MagicMock()
    # Mocking start method, it will be wrapped in to_thread, so it doesn't need to be async mock itself
    # but the orchestrator calls it.
    agent.start = MagicMock()

    strategy = MagicMock()
    strategy.execute = AsyncMock(return_value=DefenseResult(success=True))

    return Orchestrator(agent, [strategy])

@pytest.mark.asyncio
async def test_run_cycle_success(orchestrator):
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1
        result = await orchestrator.run_cycle("task", "branch")
        assert result
        orchestrator.agent.start.assert_called_once()
        orchestrator.strategies[0].execute.assert_called_once()

@pytest.mark.asyncio
async def test_run_cycle_failure_retry(orchestrator):
    # Fail first time, succeed second time
    orchestrator.strategies[0].execute.side_effect = [
        DefenseResult(success=False, message="failed"),
        DefenseResult(success=True, message="passed")
    ]

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 2
        result = await orchestrator.run_cycle("task", "branch")
        assert result
        assert orchestrator.agent.start.call_count == 2
        assert orchestrator.strategies[0].execute.call_count == 2

@pytest.mark.asyncio
async def test_run_cycle_failure_max_retries(orchestrator):
    orchestrator.strategies[0].execute.return_value = DefenseResult(success=False, message="failed")

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1
        result = await orchestrator.run_cycle("task", "branch")
        assert not result

@pytest.mark.asyncio
async def test_run_cycle_agent_exception(orchestrator):
    orchestrator.agent.start.side_effect = Exception("Agent crashed")

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1
        result = await orchestrator.run_cycle("task", "branch")
        assert not result
