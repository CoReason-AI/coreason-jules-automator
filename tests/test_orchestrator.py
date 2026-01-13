from typing import Any, Dict
from unittest.mock import MagicMock, patch

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.events import EventType
from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy


class MockStrategy(DefenseStrategy):
    def __init__(self, success: bool = True):
        self.should_succeed = success

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        return DefenseResult(success=self.should_succeed, message="Mock result")


def test_orchestrator_events() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result = orchestrator.run_cycle("task", "branch")

        assert result is True

        # Verify calls
        assert mock_emitter.emit.call_count >= 3  # Cycle start, Phase start (iter), Success

        # Check cycle start
        args, _ = mock_emitter.emit.call_args_list[0]
        event = args[0]
        assert event.type == EventType.CYCLE_START
        assert event.payload["branch"] == "branch"


def test_orchestrator_failure_events() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    mock_strategy = MockStrategy(success=False)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result = orchestrator.run_cycle("task", "branch")

        assert result is False

        # Check error emission at end
        # We expect: Cycle Start, Iteration Start, Retry/Fail, Max Retries Error
        calls = mock_emitter.emit.call_args_list
        assert len(calls) >= 4

        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Max retries reached" in last_event.message


def test_orchestrator_agent_failure_events() -> None:
    """Test that events are emitted when the agent raises an exception."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.start.side_effect = RuntimeError("Agent crash")
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result = orchestrator.run_cycle("task", "branch")

        assert result is False

        # Verify calls
        # We expect: Cycle Start, Phase Start, then Error
        assert mock_emitter.emit.call_count >= 3

        calls = mock_emitter.emit.call_args_list
        # The last event should be the agent error
        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Agent failed to execute" in last_event.message
        assert "Agent crash" in last_event.payload["error"]
