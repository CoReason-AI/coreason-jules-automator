import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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


@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_popen: MagicMock, agent: JulesAgent
) -> None:
    """Test successful session launch."""
    mock_settings.return_value.repo_name = "test/repo"

    # Simulate pre-SIDs and post-SIDs
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.communicate.return_value = ("stdout", "stderr")
    mock_process.poll.return_value = None  # Process running
    mock_popen.return_value = mock_process

    sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_popen.assert_called_once()
    assert "new" in mock_popen.call_args[0][0]
    assert "--repo" in mock_popen.call_args[0][0]
    assert "test/repo" in mock_popen.call_args[0][0]


@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_with_spec(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_popen: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch with SPEC.md injection."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.communicate.return_value = ("stdout", "stderr")
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="Spec Content"):
            sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_process.stdin.write.assert_called()
    call_args = mock_process.stdin.write.call_args[0][0]
    assert "Context from SPEC.md" in call_args
    assert "Spec Content" in call_args


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
    mock_process.poll.return_value = 1  # Exited with error
    mock_process.communicate.return_value = ("stdout", "Error Message")
    mock_process.returncode = 1
    mock_popen.return_value = mock_process

    with patch("time.sleep", return_value=None):
        sid = agent.launch_session("Test Task")

    assert sid is None


@patch("subprocess.Popen")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_popen: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch timeout."""
    mock_settings.return_value.repo_name = "test/repo"

    # Simulate no new SID appearing
    mock_get_sids.return_value = {"100"}

    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.communicate.return_value = ("stdout", "stderr")
    mock_process.poll.return_value = None  # Process running
    mock_popen.return_value = mock_process

    # To avoid long wait in tests, we can mock time.sleep or reduce range
    # But since loop is hardcoded range(1, 21), we should patch sleep
    with patch("time.sleep", return_value=None):
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


@patch("subprocess.run")
def test_wait_for_completion_success(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion success."""
    # First call running, second call completed
    mock_run.side_effect = [
        MagicMock(stdout="123 running"),
        MagicMock(stdout="123 completed"),
    ]

    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")

    assert result is True


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
    mock_run.return_value = MagicMock()  # Success

    # Mock glob to return a jules folder
    with patch("pathlib.Path.glob", return_value=[MagicMock(name="jules-123")]):
        # Mock exists for syncing
        with patch("pathlib.Path.exists", return_value=True):
            result = agent.teleport_and_sync("123", Path("/tmp"))

    assert result is True
    mock_run.assert_called_once()
    assert "teleport" in mock_run.call_args[0][0]
    assert "123" in mock_run.call_args[0][0]
    mock_copytree.assert_called()  # Should copy src and tests
    mock_copy2.assert_called()  # Should copy requirements.txt


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
