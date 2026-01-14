from typing import Any, Dict, Tuple
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.events import EventType
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.strategies.base import DefenseResult, DefenseStrategy


class MockStrategy(DefenseStrategy):
    def __init__(self, success: bool = True):
        self.should_succeed = success

    def execute(self, context: Dict[str, Any]) -> DefenseResult:
        return DefenseResult(success=self.should_succeed, message="Mock result")


def test_orchestrator_events() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    # Setup happy path
    mock_agent.launch_session.return_value = "123"
    mock_agent.wait_for_completion.return_value = True
    mock_agent.teleport_and_sync.return_value = True

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result, _ = orchestrator.run_cycle("task", "branch")

        assert result is True

        # Verify calls
        assert mock_emitter.emit.call_count >= 5
        # Cycle Start, Phase Start, Launch Running, Launch Result, Wait Running,
        # Wait Result(implicit?), Teleport Running, Teleport Result, Strategy Result

        # Check cycle start
        args, _ = mock_emitter.emit.call_args_list[0]
        event = args[0]
        assert event.type == EventType.CYCLE_START
        assert event.payload["branch"] == "branch"

        # Verify call chain
        mock_agent.launch_session.assert_called_once()
        mock_agent.wait_for_completion.assert_called_once_with("123")
        # We don't need to patch cwd here, just check it was called with a path
        args, _ = mock_agent.teleport_and_sync.call_args
        assert args[0] == "123"
        assert args[1] is not None  # Check it is a path


def test_orchestrator_failure_events() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.launch_session.return_value = "123"
    mock_agent.wait_for_completion.return_value = True
    mock_agent.teleport_and_sync.return_value = True

    mock_strategy = MockStrategy(success=False)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result, _ = orchestrator.run_cycle("task", "branch")

        assert result is False

        # Check error emission at end
        calls = mock_emitter.emit.call_args_list
        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Max retries reached" in last_event.message


def test_orchestrator_agent_failure_launch() -> None:
    """Test that events are emitted when the agent fails to launch session."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.launch_session.return_value = None  # Failed to launch

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result, _ = orchestrator.run_cycle("task", "branch")

        assert result is False

        calls = mock_emitter.emit.call_args_list
        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Agent workflow failed" in last_event.message
        assert "Failed to obtain Session ID" in last_event.payload["error"]


def test_orchestrator_agent_failure_wait() -> None:
    """Test that events are emitted when the agent fails to wait for completion."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.launch_session.return_value = "123"
    mock_agent.wait_for_completion.return_value = False  # Failed waiting

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result, _ = orchestrator.run_cycle("task", "branch")

        assert result is False

        calls = mock_emitter.emit.call_args_list
        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Agent workflow failed" in last_event.message
        assert "did not complete successfully" in last_event.payload["error"]


def test_orchestrator_agent_failure_teleport() -> None:
    """Test that events are emitted when the agent fails to teleport."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.launch_session.return_value = "123"
    mock_agent.wait_for_completion.return_value = True
    mock_agent.teleport_and_sync.return_value = False  # Failed teleport

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 1

        result, _ = orchestrator.run_cycle("task", "branch")

        assert result is False

        calls = mock_emitter.emit.call_args_list
        last_event = calls[-1][0][0]
        assert last_event.type == EventType.ERROR
        assert "Agent workflow failed" in last_event.message
        assert "Failed to sync remote code" in last_event.payload["error"]


def test_run_campaign_success() -> None:
    """Test successful campaign execution."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        mock_run_cycle.return_value = (True, "Success")
        mock_git.get_commit_log.return_value = "raw log"
        mock_janitor.professionalize_commit.return_value = "clean message"

        orchestrator.run_campaign("task", "base", iterations=2)

        # 1 agg checkout + 2 iterations * 1 checkout = 3 checkouts
        assert mock_git.checkout_new_branch.call_count == 3
        assert mock_run_cycle.call_count == 2
        assert mock_git.merge_squash.call_count == 2


def test_run_campaign_missing_deps() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        # missing git and janitor
    )

    with pytest.raises(RuntimeError, match="GitInterface and JanitorService are required"):
        orchestrator.run_campaign("task")


def test_run_campaign_iteration_error() -> None:
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        # First iteration raises exception, Second succeeds (to check continuation)
        mock_run_cycle.side_effect = [Exception("Loop Error"), (True, "Success")]
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.professionalize_commit.return_value = "msg"

        orchestrator.run_campaign("task", iterations=2)

        # Verify called twice
        assert mock_run_cycle.call_count == 2


def test_run_campaign_failure_continue() -> None:
    """Test campaign continuation on cycle failure (False return)."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        # First fails, Second succeeds
        mock_run_cycle.side_effect = [(False, "Cycle Failed"), (True, "Success")]
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.professionalize_commit.return_value = "msg"

        orchestrator.run_campaign("task", iterations=2)

        # Verify called twice
        assert mock_run_cycle.call_count == 2
        # Verify warning was logged (implicit via coverage, or we could patch logger)


def test_run_campaign_infinite_success() -> None:
    """Test infinite campaign breaking on mission completion."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False  # Initially false

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        mock_run_cycle.return_value = (True, "Success")
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.professionalize_commit.return_value = "msg"

        # Side effect to set mission_complete after 2nd call
        def side_effect(*args: Any, **kwargs: Any) -> Tuple[bool, str]:
            if mock_run_cycle.call_count >= 2:
                mock_agent.mission_complete = True
            return (True, "Success")

        mock_run_cycle.side_effect = side_effect

        # Run with iterations=0 (infinite)
        orchestrator.run_campaign("task", iterations=0)

        assert mock_run_cycle.call_count == 2
        # Check that it stopped


def test_run_campaign_safety_limit() -> None:
    """Test infinite campaign hitting safety limit."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
    )

    # Set safety limit low for test
    orchestrator.SAFETY_LIMIT = 2

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        mock_run_cycle.return_value = (True, "Success")
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.professionalize_commit.return_value = "msg"

        # Run with iterations=0 (infinite)
        orchestrator.run_campaign("task", iterations=0)

        # It should run 1, 2, then check limit > 2, break?
        # i=1 (run), i=2 (run), i=3 (check safety limit? No.
        # Loop:
        # i=1
        # check safety: 0 and 1 > 2? False.
        # run cycle
        # i++ (i=2)
        # i=2
        # check safety: 2 > 2? False.
        # run cycle
        # i++ (i=3)
        # i=3
        # check safety: 3 > 2? True. Break.

        assert mock_run_cycle.call_count == 2
