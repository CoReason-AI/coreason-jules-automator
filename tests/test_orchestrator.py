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
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        mock_run_cycle.return_value = (True, "Success")
        mock_git.get_commit_log.return_value = "raw log"
        # Setup Janitor mocks for Sans-I/O
        mock_req = MagicMock()
        mock_janitor.build_professionalize_request.return_value = mock_req
        mock_client.complete.return_value = '{"commit_text": "clean message"}'
        mock_janitor.parse_professionalize_response.return_value = "clean message"

        orchestrator.run_campaign("task", "base", iterations=2)

        # 1 agg checkout + 2 iterations * 1 checkout = 3 checkouts
        assert mock_git.checkout_new_branch.call_count == 3
        assert mock_run_cycle.call_count == 2
        assert mock_git.merge_squash.call_count == 2
        # Verify cleanup
        assert mock_git.delete_branch.call_count == 2
        # Verify LLM interaction
        assert mock_janitor.build_professionalize_request.called
        assert mock_client.complete.called
        assert mock_janitor.parse_professionalize_response.called


def test_run_campaign_completion() -> None:
    """Test campaign stops when mission_complete is detected."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False  # Default

    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    call_counter = 0

    def side_effect(*args: Any, **kwargs: Any) -> Tuple[bool, str]:
        nonlocal call_counter
        call_counter += 1
        if call_counter >= 2:
            mock_agent.mission_complete = True
        return (True, "Success")

    with patch.object(orchestrator, "run_cycle", side_effect=side_effect) as mock_run_cycle:
        mock_git.get_commit_log.return_value = "raw log"
        mock_janitor.build_professionalize_request.return_value = MagicMock()
        mock_janitor.parse_professionalize_response.return_value = "clean"
        mock_client.complete.return_value = "{}"

        orchestrator.run_campaign("task", iterations=10)

        # Should stop after 2 iterations because mission_complete became True
        assert mock_run_cycle.call_count == 2
        assert mock_git.delete_branch.call_count == 2


def test_run_campaign_cleanup_exception() -> None:
    """Test cleanup failure handling during exception recovery."""
    mock_agent = MagicMock(spec=JulesAgent)
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

    # Trigger exception in run_cycle
    with patch.object(orchestrator, "run_cycle", side_effect=Exception("Cycle Error")):
        # Trigger exception in delete_branch (cleanup)
        mock_git.delete_branch.side_effect = Exception("Cleanup Error")

        # Should not crash
        orchestrator.run_campaign("task", iterations=1)

        # Verify run_cycle called
        # Note: run_campaign calls run_cycle inside the loop
        # Verify delete_branch called
        assert mock_git.delete_branch.called


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
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        # First iteration raises exception, Second succeeds (to check continuation)
        mock_run_cycle.side_effect = [Exception("Loop Error"), (True, "Success")]
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.build_professionalize_request.return_value = MagicMock()
        mock_client.complete.return_value = "{}"
        mock_janitor.parse_professionalize_response.return_value = "clean"

        orchestrator.run_campaign("task", iterations=2)

        # Verify called twice
        assert mock_run_cycle.call_count == 2


def test_run_campaign_failure_continue() -> None:
    """Test campaign continuation on cycle failure (False return)."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        # First fails, Second succeeds
        mock_run_cycle.side_effect = [(False, "Cycle Failed"), (True, "Success")]
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.build_professionalize_request.return_value = MagicMock()
        mock_client.complete.return_value = "{}"
        mock_janitor.parse_professionalize_response.return_value = "clean"

        orchestrator.run_campaign("task", iterations=2)

        # Verify called twice
        assert mock_run_cycle.call_count == 2
        # Verify warning was logged (implicit via coverage, or we could patch logger)


def test_orchestrator_retry_feedback() -> None:
    """Test that feedback is appended to the task description on retry."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.launch_session.return_value = "123"
    mock_agent.wait_for_completion.return_value = True
    mock_agent.teleport_and_sync.return_value = True

    mock_strategy = MagicMock(spec=DefenseStrategy)
    # First call returns failure, second returns success
    mock_strategy.execute.side_effect = [
        DefenseResult(success=False, message="First failure"),
        DefenseResult(success=True, message="Second success"),
    ]

    mock_emitter = MagicMock()

    orchestrator = Orchestrator(agent=mock_agent, strategies=[mock_strategy], event_emitter=mock_emitter)

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 2

        result, msg = orchestrator.run_cycle("original task", "branch")

        assert result is True
        assert msg == "Success"

        # Check that launch_session was called twice
        assert mock_agent.launch_session.call_count == 2

        # Check first call args
        first_call_args = mock_agent.launch_session.call_args_list[0]
        assert first_call_args[0][0] == "original task"

        # Check second call args
        second_call_args = mock_agent.launch_session.call_args_list[1]
        task_arg = second_call_args[0][0]
        assert "original task" in task_arg
        assert "IMPORTANT: The previous attempt failed" in task_arg
        assert "First failure" in task_arg


def test_run_campaign_infinite() -> None:
    """Test infinite campaign execution (runs until limit or mission complete)."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
        mock_git.get_commit_log.return_value = "log"
        mock_janitor.build_professionalize_request.return_value = MagicMock()
        mock_client.complete.return_value = "{}"
        mock_janitor.parse_professionalize_response.return_value = "clean"

        call_counter = 0

        def side_effect(*args: Any, **kwargs: Any) -> Tuple[bool, str]:
            nonlocal call_counter
            call_counter += 1
            if call_counter >= 3:
                mock_agent.mission_complete = True
            return (True, "Success")

        mock_run_cycle.side_effect = side_effect

        # Test with iterations=0 (infinite)
        orchestrator.run_campaign("task", iterations=0)

        # It should run 3 times and stop because mission_complete became true
        assert mock_run_cycle.call_count == 3


def test_run_campaign_professionalize_exception() -> None:
    """Test fallback when professionalization fails."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False  # Default
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    # Patch random.choices to have predictable ID for branch naming
    with patch("random.choices", return_value=["1", "2", "3"]):
        # run_id will be "123"
        # agg_branch: vibe_run_123
        # iter_branch: vibe_run_123_001

        with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
            mock_run_cycle.return_value = (True, "Success")
            mock_git.get_commit_log.return_value = "raw log"

            # Trigger exception in professionalize request
            mock_janitor.build_professionalize_request.side_effect = Exception("Build Error")

            # Mock sanitize so we can verify fallback
            mock_janitor.sanitize_commit.return_value = "sanitized fallback"

            orchestrator.run_campaign("task", iterations=1)

            mock_git.merge_squash.assert_called_with("vibe_run_123_001", "vibe_run_123", "raw log")


def test_run_campaign_professionalize_no_client() -> None:
    """Test professionalization logic when no client is present."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)

    # Initialize without llm_client
    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=None,
    )

    with patch("random.choices", return_value=["1", "2", "3"]):
        with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
            mock_run_cycle.return_value = (True, "Success")
            mock_git.get_commit_log.return_value = "raw log"
            mock_janitor.sanitize_commit.return_value = "sanitized"

            orchestrator.run_campaign("task", iterations=1)

            # verify sanitize_commit was called and used for merge
            mock_janitor.sanitize_commit.assert_called_with("raw log")
            mock_git.merge_squash.assert_called_with("vibe_run_123_001", "vibe_run_123", "sanitized")


def test_run_campaign_retry_loop_fail() -> None:
    """Test retry loop exhaustion in professionalize commit."""
    mock_agent = MagicMock(spec=JulesAgent)
    mock_agent.mission_complete = False
    mock_strategy = MockStrategy(success=True)
    mock_emitter = MagicMock()
    mock_git = MagicMock(spec=GitInterface)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_client = MagicMock()

    orchestrator = Orchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        event_emitter=mock_emitter,
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_client,
    )

    with patch("random.choices", return_value=["1", "2", "3"]):
        with patch.object(orchestrator, "run_cycle") as mock_run_cycle:
            mock_run_cycle.return_value = (True, "Success")
            mock_git.get_commit_log.return_value = "raw log"

            mock_janitor.build_professionalize_request.return_value = MagicMock()

            # Client execution fails every time
            mock_client.complete.side_effect = Exception("Exec Error")

            orchestrator.run_campaign("task", iterations=1)

            # Should fall back to raw log (initial value of clean_msg)
            mock_git.merge_squash.assert_called_with("vibe_run_123_001", "vibe_run_123", "raw log")
            # Verify called 3 times (loop range 3)
            assert mock_client.complete.call_count == 3
