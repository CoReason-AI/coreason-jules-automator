from unittest.mock import MagicMock, patch

import pexpect
import pytest

from coreason_jules_automator.agent.jules import JulesAgent


@pytest.fixture
def agent() -> JulesAgent:
    return JulesAgent()


def test_start_with_spec(agent: JulesAgent) -> None:
    """Test start injects SPEC.md context."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="Spec content"):
            with patch("pexpect.spawn") as mock_spawn:
                mock_child = MagicMock()
                mock_child.exitstatus = 0
                mock_spawn.return_value = mock_child

                # Mock expect loop to exit immediately (EOF)
                mock_child.expect.return_value = 1

                agent.start("Task 1")

                # Verify sendline called with context
                mock_child.sendline.assert_called()
                args, _ = mock_child.sendline.call_args
                assert "Spec content" in args[0]
                assert "Task 1" in args[0]


def test_start_without_spec(agent: JulesAgent) -> None:
    """Test start without SPEC.md."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 0
            mock_spawn.return_value = mock_child
            mock_child.expect.return_value = 1  # EOF

            agent.start("Task 1")

            args, _ = mock_child.sendline.call_args
            assert "Spec content" not in args[0]
            assert "Task 1" in args[0]


def test_interaction_loop_auto_reply(agent: JulesAgent) -> None:
    """Test auto-reply logic."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 0
            mock_spawn.return_value = mock_child

            # Sequence: Match "Should I" -> Match EOF
            mock_child.expect.side_effect = [0, 1]

            agent.start("Task")

            # Verify auto-reply sent
            mock_child.sendline.assert_any_call("Use your best judgment.")


def test_start_spawn_failure(agent: JulesAgent) -> None:
    """Test failure to spawn."""
    with patch("pexpect.spawn", side_effect=pexpect.ExceptionPexpect("Failed")):
        with pytest.raises(RuntimeError) as excinfo:
            agent.start("Task")
        assert "Failed to start Jules" in str(excinfo.value)


def test_spec_read_failure(agent: JulesAgent) -> None:
    """Test SPEC.md read failure handled gracefully."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", side_effect=OSError("Read error")):
            with patch("pexpect.spawn") as mock_spawn:
                mock_child = MagicMock()
                mock_child.exitstatus = 0
                mock_spawn.return_value = mock_child
                mock_child.expect.return_value = 1

                agent.start("Task")

                # Should proceed without context
                args, _ = mock_child.sendline.call_args
                assert "Task" in args[0]
                # Log warning should be called (verified implicitly by no crash)


def test_interaction_loop_timeout(agent: JulesAgent) -> None:
    """Test timeout handling in loop."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 0
            mock_spawn.return_value = mock_child

            # Sequence: TIMEOUT (alive) -> TIMEOUT (dead)
            mock_child.expect.side_effect = [2, 2]
            mock_child.isalive.side_effect = [True, False]

            agent.start("Task")

            assert mock_child.close.called


def test_interaction_loop_eof_exception(agent: JulesAgent) -> None:
    """Test EOF exception handling."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 0
            mock_spawn.return_value = mock_child
            mock_child.expect.side_effect = pexpect.EOF("EOF")

            agent.start("Task")
            assert mock_child.close.called


def test_interaction_loop_timeout_exception(agent: JulesAgent) -> None:
    """Test TIMEOUT exception handling (not return value)."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 0
            mock_spawn.return_value = mock_child
            mock_child.expect.side_effect = [pexpect.TIMEOUT("Time"), pexpect.EOF("End")]
            mock_child.isalive.side_effect = [True, False]  # Continue, then break

            agent.start("Task")
            assert mock_child.close.called


def test_interaction_loop_exit_status(agent: JulesAgent) -> None:
    """Test logging warning on non-zero exit status."""
    with patch("pathlib.Path.exists", return_value=False):
        with patch("pexpect.spawn") as mock_spawn:
            mock_child = MagicMock()
            mock_child.exitstatus = 1  # Non-zero
            mock_spawn.return_value = mock_child
            mock_child.expect.return_value = 1  # EOF

            # Mock logger to verify warning
            with patch("coreason_jules_automator.agent.jules.logger") as mock_logger:
                agent.start("Task")
                mock_logger.warning.assert_called_with("Jules exited with status 1")


def test_interaction_loop_no_child(agent: JulesAgent) -> None:
    """Test _interaction_loop with no child."""
    agent.child = None
    agent._interaction_loop()
    # Should just return


def test_agent_exit_status_warning() -> None:
    """Test JulesAgent logging warning when exit status is non-zero."""
    agent = JulesAgent()
    with patch("pexpect.spawn") as mock_spawn:
        mock_child = MagicMock()
        mock_child.exitstatus = 1
        mock_spawn.return_value = mock_child
        mock_child.expect.return_value = 1  # EOF

        with patch("coreason_jules_automator.agent.jules.logger") as mock_logger:
            agent.start("Task")
            mock_logger.warning.assert_called_with("Jules exited with status 1")
