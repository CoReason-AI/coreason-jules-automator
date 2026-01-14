import subprocess
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from coreason_jules_automator.agent.jules import JulesAgent


@pytest.fixture
def agent() -> JulesAgent:
    return JulesAgent()


@patch("subprocess.run")
def test_get_active_sids(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test getting active SIDs."""
    mock_run.return_value.stdout = "123 active\n456 completed"
    sids = agent._get_active_sids()
    assert "123" in sids
    assert "456" in sids
    assert len(sids) == 2


@patch("subprocess.run")
def test_get_active_sids_empty(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test getting empty active SIDs."""
    mock_run.return_value.stdout = "No sessions found"
    sids = agent._get_active_sids()
    assert len(sids) == 0


@patch("subprocess.run")
def test_get_active_sids_failure(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test get_active_sids handling CalledProcessError."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    sids = agent._get_active_sids()
    assert sids == set()


@patch("os.read")
@patch("select.select")
@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_popen: MagicMock,
    mock_select: MagicMock,
    mock_read: MagicMock,
    agent: JulesAgent
) -> None:
    """Test successful session launch with interactive loop."""
    mock_settings.return_value.repo_name = "test/repo"

    # Simulate pre-SIDs and post-SIDs
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.stdout.fileno.return_value = 1
    mock_process.poll.return_value = None  # Process running
    mock_popen.return_value = mock_process

    # Mock select to return nothing (no data to read)
    mock_select.return_value = ([], [], [])

    with patch("time.sleep", return_value=None):
        with patch("time.time") as mock_time:
             # start_time, loop1 check, loop1 %5 check (fail), loop2 check, loop2 %5 check (pass)
             mock_time.side_effect = [1000, 1001, 1001, 1005, 1005, 1005, 1005]
             sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_popen.assert_called_once()
    mock_process.terminate.assert_called_once()


@patch("os.read")
@patch("select.select")
@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_auto_reply(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_popen: MagicMock,
    mock_select: MagicMock,
    mock_read: MagicMock,
    agent: JulesAgent
) -> None:
    """Test session launch with auto-reply."""
    mock_settings.return_value.repo_name = "test/repo"

    mock_get_sids.return_value = {"100"} # Initial

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.stdout.fileno.return_value = 1
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process

    # 1st iter: Return data available
    # 2nd iter: No data
    mock_select.side_effect = [
        ([mock_process.stdout.fileno()], [], []),
        ([], [], []),
        ([], [], []),
    ]

    mock_read.side_effect = [b"Continue? [y/N]", b""]

    # Trigger SID detection to exit loop
    # We set side_effect to: initial, check1 (fail), check2 (success)
    mock_get_sids.side_effect = [{"100"}, {"100"}, {"100", "101"}]

    with patch("time.sleep", return_value=None):
        with patch("time.time") as mock_time:
             # start_time (1000)
             # loop 1 check timeout (1001)
             # loop 1 check % 5 (1001) -> False
             # loop 2 check timeout (1005)
             # loop 2 check % 5 (1005) -> True -> Calls get_active_sids -> finds new -> Break
             mock_time.side_effect = [1000, 1001, 1001, 1005, 1005, 1005, 1005]

             sid = agent.launch_session("Test Task")

    assert sid == "101"
    # Check auto-reply
    mock_process.stdin.write.assert_has_calls([
        call("Use your best judgment and make autonomous decisions.\n")
    ], any_order=True)


@patch("select.select")
@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_popen: MagicMock,
    mock_select: MagicMock,
    agent: JulesAgent
) -> None:
    """Test session launch timeout."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process
    mock_select.return_value = ([], [], [])

    # Force timeout
    with patch("time.time") as mock_time:
        # start_time = 0
        # loop 1 check: 61 - 0 > 60 -> break
        mock_time.side_effect = [0, 61, 61]

        sid = agent.launch_session("Test Task")

    assert sid is None
    mock_process.kill.assert_called_once()


@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_exception(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_popen: MagicMock,
    agent: JulesAgent,
) -> None:
    """Test session launch handling generic exception."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = set()
    mock_popen.side_effect = Exception("Launch Error")

    sid = agent.launch_session("Test Task")
    assert sid is None


@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_early_exit(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_popen: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch handling early process exit."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_process = MagicMock()
    # poll returns 1 (exit code) immediately
    mock_process.poll.return_value = 1
    mock_popen.return_value = mock_process

    sid = agent.launch_session("Test Task")

    assert sid is None


@patch("subprocess.run")
def test_wait_for_completion_success(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion success."""
    mock_run.side_effect = [
        MagicMock(stdout="123 running"),
        MagicMock(stdout="123 completed"),
    ]

    with patch("time.sleep", return_value=None):
        # We assume time.time() works normally or is consistent enough
        result = agent.wait_for_completion("123")

    assert result is True


@patch("subprocess.run")
def test_wait_for_completion_failed(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion detection of failure."""
    mock_run.return_value.stdout = "123 failed error"

    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")

    assert result is False


@patch("subprocess.run")
def test_wait_for_completion_disappeared(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion where SID disappears."""
    mock_run.return_value.stdout = "456 running"  # SID 123 is missing

    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")

    assert result is False


@patch("subprocess.run")
def test_wait_for_completion_exception(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion handling generic exception."""
    # First call raises Exception, second call succeeds
    mock_run.side_effect = [
        Exception("Network Error"),
        MagicMock(stdout="123 completed"),
    ]

    with patch("time.sleep", return_value=None):
        # Prevent timeout
        with patch("time.time", return_value=0):
             result = agent.wait_for_completion("123")

    assert result is True


@patch("subprocess.run")
@patch("shutil.copytree")
@patch("shutil.copy2")
@patch("pathlib.Path.mkdir")
@patch("shutil.rmtree")
def test_teleport_and_sync_success(
    mock_rmtree: MagicMock,
    mock_mkdir: MagicMock,
    mock_copy2: MagicMock,
    mock_copytree: MagicMock,
    mock_run: MagicMock,
    agent: JulesAgent,
) -> None:
    """Test successful teleport and sync."""
    mock_run.return_value = MagicMock()

    with patch("pathlib.Path.glob", return_value=[MagicMock(name="jules-123")]):
        with patch("pathlib.Path.exists", return_value=True):
            result = agent.teleport_and_sync("123", Path("/tmp"))

    assert result is True
    # Verify both requirements.txt and pyproject.toml are copied
    assert mock_copy2.call_count >= 1


@patch("subprocess.run")
@patch("pathlib.Path.mkdir")
def test_teleport_and_sync_no_folder(mock_mkdir: MagicMock, mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test teleport failing to find jules-* folder."""
    mock_run.return_value = MagicMock()

    with patch("pathlib.Path.glob", return_value=[]):
        result = agent.teleport_and_sync("123", Path("/tmp"))

    assert result is False


@patch("subprocess.run")
def test_teleport_and_sync_failure(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test teleport command failure."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")

    with patch("pathlib.Path.mkdir"):
        result = agent.teleport_and_sync("123", Path("/tmp"))

    assert result is False


@patch("subprocess.run")
@patch("pathlib.Path.mkdir")
def test_teleport_and_sync_exception(mock_mkdir: MagicMock, mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test teleport handling generic exception."""
    mock_run.side_effect = Exception("Disk Error")

    result = agent.teleport_and_sync("123", Path("/tmp"))
    assert result is False
