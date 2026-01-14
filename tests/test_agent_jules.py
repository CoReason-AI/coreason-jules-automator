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


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success_polling(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test successful session launch via polling (pexpect timeout loop)."""
    mock_settings.return_value.repo_name = "test/repo"

    # Simulate pre-SIDs and post-SIDs
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}, {"100", "101"}]

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child

    # Simulate expect returning TIMEOUT (4) then EOF (3)
    # 4 -> poll -> find SID -> store it
    # 3 -> break -> return stored SID
    mock_child.expect.side_effect = [4, 3]
    mock_child.isalive.return_value = False

    sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_spawn.assert_called_once()
    mock_child.sendline.assert_called_once()  # Initial prompt


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success_pattern(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test successful session launch via output pattern matching."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child

    # Simulate finding SID pattern (2) then EOF (3)
    mock_child.expect.side_effect = [2, 3]
    mock_child.match.group.return_value = "202"
    mock_child.isalive.return_value = False

    sid = agent.launch_session("Test Task")

    assert sid == "202"


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_interaction(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch handling interactive questions."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child

    # 0 (Question) -> 0 (Question) -> 2 (SID) -> 3 (EOF)
    mock_child.expect.side_effect = [0, 0, 2, 3]
    mock_child.match.group.return_value = "303"
    mock_child.isalive.return_value = False

    sid = agent.launch_session("Test Task")

    assert sid == "303"
    # Initial prompt + 2 auto-replies = 3 sendline calls
    assert mock_child.sendline.call_count == 3
    # Check args for auto-reply
    args = mock_child.sendline.call_args_list
    assert "Use your best judgment" in args[1][0][0]
    assert "Use your best judgment" in args[2][0][0]


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_mission_complete(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test detecting mission completion signal."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child

    # 1 (Success) -> 2 (SID) -> 3 (EOF)
    mock_child.expect.side_effect = [1, 2, 3]
    mock_child.match.group.return_value = "404"
    mock_child.isalive.return_value = False

    sid = agent.launch_session("Test Task")

    assert sid == "404"
    assert agent.mission_complete is True


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_with_spec(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch with SPEC.md injection."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.expect.return_value = 3  # EOF immediately
    mock_child.isalive.return_value = False

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="Spec Content"):
            agent.launch_session("Test Task")

    mock_child.sendline.assert_called()
    call_args = mock_child.sendline.call_args[0][0]
    assert "Context from SPEC.md" in call_args
    assert "Spec Content" in call_args


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout_loop(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch timeout (total time exceeded)."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = True  # Stays alive

    # Simulate loop running for a while then stopping by logic
    # We patch time.time to simulate timeout

    # In launch_session:
    # start_time = time.time()
    # while (time.time() - start_time) < 1800:

    with patch("time.time", side_effect=[1000, 1001, 2900]):  # Start, First loop OK, Second loop Timeout
        mock_child.expect.return_value = 4  # TIMEOUT
        sid = agent.launch_session("Test Task")

    assert sid is None
    mock_child.close.assert_called()


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
def test_wait_for_completion_pre_detected(mock_run: MagicMock, agent: JulesAgent) -> None:
    """Test wait for completion when already detected."""
    agent.mission_complete = True
    result = agent.wait_for_completion("123")
    assert result is True
    mock_run.assert_not_called()


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


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_exception(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test launch session generic exception."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = set()
    mock_spawn.side_effect = Exception("Spawn failed")

    sid = agent.launch_session("Task")
    assert sid is None


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout_loop_final_failure(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch timeout where final SID check also fails (lines 143-145)."""
    mock_settings.return_value.repo_name = "test/repo"
    mock_get_sids.return_value = {"100"}  # No new SID

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = True

    # 1000 -> Start
    # 1001 -> First iteration (TIMEOUT)
    # 2900 -> Loop condition check (End)
    with patch("time.time", side_effect=[1000, 1001, 2900]):
        mock_child.expect.return_value = 4  # TIMEOUT

        # Capture logs to verify error message
        with patch("coreason_jules_automator.agent.jules.logger.error") as mock_error:
            sid = agent.launch_session("Test Task")

            assert sid is None
            mock_child.close.assert_called()
            mock_error.assert_called_with("❌ Jules failed to register a session within timeout.")


@patch("coreason_jules_automator.agent.jules.pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout_loop_race_condition(
    mock_settings: MagicMock, mock_get_sids: MagicMock, mock_spawn: MagicMock, agent: JulesAgent
) -> None:
    """Test session launch timeout where SID is found at the very end (line 143)."""
    mock_settings.return_value.repo_name = "test/repo"

    # 1. Start: {"100"}
    # 2. Inside Loop (TIMEOUT): {"100"} (Not found)
    # 3. Final Check: {"100", "101"} (Found!)
    mock_get_sids.side_effect = [{"100"}, {"100"}, {"100", "101"}]

    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = True

    # 1000 -> Start
    # 1001 -> First iteration (TIMEOUT)
    # 2900 -> Loop condition check (End)
    with patch("time.time", side_effect=[1000, 1001, 2900]):
        mock_child.expect.return_value = 4  # TIMEOUT

        sid = agent.launch_session("Test Task")

        assert sid == "101"
        mock_child.close.assert_called()
