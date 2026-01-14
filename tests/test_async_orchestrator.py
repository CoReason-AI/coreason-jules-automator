from unittest.mock import AsyncMock, MagicMock

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.orchestrator import AsyncOrchestrator
from coreason_jules_automator.async_api.strategies import AsyncDefenseStrategy
from coreason_jules_automator.strategies.base import DefenseResult


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COREASON_REPO_NAME", "dummy/repo")
    monkeypatch.setenv("COREASON_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("COREASON_GOOGLE_API_KEY", "dummy_key")


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_success() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid-123")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=True, message="All good"))

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is True
    assert feedback == "Success"

    mock_agent.launch_session.assert_awaited_once()
    mock_agent.wait_for_completion.assert_awaited_once_with("sid-123")
    mock_agent.teleport_and_sync.assert_awaited_once()
    mock_strategy.execute.assert_awaited_once()

    # Check context passed to strategy
    call_args = mock_strategy.execute.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    context = kwargs.get("context")
    assert context is not None
    assert context["sid"] == "sid-123"
    assert context["branch_name"] == "feature/bugfix"


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_retry() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(side_effect=["sid-1", "sid-2"])
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    # Fail first time, succeed second time
    mock_strategy.execute = AsyncMock(side_effect=[
        DefenseResult(success=False, message="Lint error"),
        DefenseResult(success=True, message="All good")
    ])

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is True
    assert feedback == "Success"

    assert mock_agent.launch_session.call_count == 2
    assert mock_agent.wait_for_completion.call_count == 2
    assert mock_strategy.execute.call_count == 2

    # Verify feedback injection in second call
    call_args_list = mock_agent.launch_session.call_args_list
    first_call_arg = call_args_list[0][0][0]
    second_call_arg = call_args_list[1][0][0]

    assert first_call_arg == "Fix bug"
    assert "Lint error" in second_call_arg
    assert "IMPORTANT" in second_call_arg


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_agent_failure() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value=None)  # Fail to launch

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is False
    assert "Failed to obtain Session ID" in feedback
    mock_strategy.execute.assert_not_awaited()
